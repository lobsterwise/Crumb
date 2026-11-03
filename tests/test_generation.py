import json
import os
import unittest
from unittest.mock import patch
from urllib.error import URLError

import server


class FakeCursor:
    def __init__(self, rows=()):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)


class FakeDatabase:
    def __init__(self, subjects):
        self.subjects = subjects
        self.lessons = []

    def execute(self, query, args=()):
        if query.startswith('SELECT subject_id FROM user_subjects'):
            return FakeCursor([{'subject_id':subject} for subject in self.subjects])
        if query.startswith('INSERT INTO user_custom_lessons'):
            self.lessons.append(args)
            return FakeCursor()
        raise AssertionError(f'Unexpected database query: {query}')


class TestHandler(server.Handler):
    def send_json(self, status, payload, headers=None):
        return status, payload


class FakeHTTPResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def valid_lesson(subject='biology'):
    return {
        'subject':subject,
        'title':'A useful lesson',
        'tag':'BIOLOGY',
        'minutes':9,
        'lead':'A short introduction.',
        'sections':[{'heading':f'Section {index + 1}','body':' '.join(['concept'] * 80)} for index in range(5)],
        'takeaway':'One useful idea.',
        'questions':[{'question':f'Question {index + 1}?','options':['First answer','Second answer','Third answer'],'answerIndex':1,'explanation':'The second answer is correct.'} for index in range(4)],
        'source':'Gemini',
    }


class GenerationTests(unittest.TestCase):
    def setUp(self):
        self.handler = object.__new__(TestHandler)

    def test_random_generation_uses_gemini_topics_and_ordered_seed_words(self):
        db = FakeDatabase(['biology', 'chemistry'])
        topic_list = {'topics':['Topic about cells','Topic about ecosystems','Topic about energy']}
        seed_words = ['ember','compass','velvet','orbit']
        with patch.dict(os.environ, {'GEMINI_API_KEY':'test-key'}, clear=True), \
             patch.object(server.secrets, 'choice', side_effect=['biology','Topic about ecosystems']), \
             patch.object(server, 'random_seed_words', return_value=seed_words), \
             patch.object(TestHandler, 'generate_gemini_json', side_effect=[topic_list,valid_lesson()]) as generate:
            status, response = self.handler.generate_lesson(db, 3, {'randomTopic':True})

        self.assertEqual(status, 201)
        self.assertEqual(response['lesson']['subject'], 'biology')
        self.assertEqual(len(generate.call_args_list), 2)
        self.assertEqual(generate.call_args_list[0].args[1], 'gemini-3.5-flash-lite')
        self.assertEqual(generate.call_args_list[1].args[1], 'gemini-3.5-flash-lite')
        topic_prompt = generate.call_args_list[0].args[2]
        lesson_prompt = generate.call_args_list[1].args[2]
        self.assertIn('biology (Biology)', topic_prompt)
        self.assertIn('ember, compass, velvet, orbit', topic_prompt)
        self.assertLess(topic_prompt.index('ember'), topic_prompt.index('orbit'))
        self.assertIn('Topic about ecosystems', lesson_prompt)
        self.assertIn('Use subject id "biology"', lesson_prompt)
        self.assertEqual(len(db.lessons), 1)
        lesson=response['lesson']
        self.assertEqual(len(lesson['sections']), 5)
        self.assertEqual(len(lesson['questions']), 4)
        self.assertGreaterEqual(len(lesson['body'].split()), 400)
        self.assertGreaterEqual(lesson['minutes'], 8)

    def test_random_generation_rejects_too_few_usable_topics(self):
        db = FakeDatabase(['biology'])
        with patch.dict(os.environ, {'GEMINI_API_KEY':'test-key'}), \
             patch.object(server.secrets, 'choice', return_value='biology'), \
             patch.object(server, 'random_seed_words', return_value=['ember','compass','velvet','orbit']), \
             patch.object(TestHandler, 'generate_gemini_json', return_value={'topics':['Only one topic','only one topic',None,'']}) as generate:
            status, response = self.handler.generate_lesson(db, 3, {'randomTopic':True})

        self.assertEqual(status, 502)
        self.assertIn('too few', response['error'])
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(db.lessons, [])

    def test_topic_provider_failure_does_not_persist_a_lesson(self):
        db = FakeDatabase(['biology'])
        with patch.dict(os.environ, {'GEMINI_API_KEY':'test-key'}), \
             patch.object(server.secrets, 'choice', return_value='biology'), \
             patch.object(server, 'random_seed_words', return_value=['ember','compass','velvet','orbit']), \
             patch.object(TestHandler, 'generate_gemini_json', side_effect=URLError('offline')):
            status, response = self.handler.generate_lesson(db, 3, {'randomTopic':True})

        self.assertEqual(status, 502)
        self.assertIn('Topic service request failed', response['error'])
        self.assertEqual(db.lessons, [])

    def test_topic_service_without_candidates_returns_controlled_error(self):
        db = FakeDatabase(['biology'])
        with patch.dict(os.environ, {'GEMINI_API_KEY':'test-key'}), \
             patch.object(server.secrets, 'choice', return_value='biology'), \
             patch.object(server, 'random_seed_words', return_value=['ember','compass','velvet','orbit']), \
             patch.object(TestHandler, 'generate_gemini_json', side_effect=IndexError):
            status, response = self.handler.generate_lesson(db, 3, {'randomTopic':True})

        self.assertEqual(status, 502)
        self.assertIn('unreadable response', response['error'])
        self.assertEqual(db.lessons, [])

    def test_random_generation_requires_saved_subjects(self):
        db = FakeDatabase([])
        with patch.object(TestHandler, 'generate_gemini_json') as generate:
            status, response = self.handler.generate_lesson(db, 3, {'randomTopic':True})

        self.assertEqual(status, 400)
        self.assertEqual(generate.call_count, 0)

    def test_random_generation_requires_gemini_key_before_provider_calls(self):
        db = FakeDatabase(['biology'])
        with patch.dict(os.environ, {'GEMINI_API_KEY':''}), \
             patch.object(TestHandler, 'generate_gemini_json') as generate:
            status, response = self.handler.generate_lesson(db, 3, {'randomTopic':True})

        self.assertEqual(status, 503)
        self.assertEqual(generate.call_count, 0)

    def test_manual_prompt_still_generates_in_one_call(self):
        db = FakeDatabase(['biology'])
        with patch.dict(os.environ, {'GEMINI_API_KEY':'test-key'}), \
             patch.object(TestHandler, 'generate_gemini_json', return_value=valid_lesson()) as generate:
            status, response = self.handler.generate_lesson(db, 3, {'prompt':'How do cells store energy?'})

        self.assertEqual(status, 201)
        self.assertEqual(generate.call_count, 1)
        self.assertIn('How do cells store energy?', generate.call_args.args[2])
        self.assertEqual(response['lesson']['subject'], 'biology')
        self.assertEqual(len(db.lessons), 1)

    def test_blank_manual_prompt_is_rejected_before_api_key_check(self):
        db = FakeDatabase([])
        with patch.dict(os.environ, {'GEMINI_API_KEY':''}), \
             patch.object(TestHandler, 'generate_gemini_json') as generate:
            status, response = self.handler.generate_lesson(db, 3, {'prompt':'  '})

        self.assertEqual(status, 400)
        self.assertIn('Enter a topic', response['error'])
        self.assertEqual(generate.call_count, 0)

    def test_gemini_helper_builds_google_generate_content_request(self):
        provider_response = {'candidates':[{'content':{'parts':[{'text':'{"topics":[]}'}]}}]}
        with patch.object(server, 'urlopen', return_value=FakeHTTPResponse(provider_response)) as urlopen:
            result = self.handler.generate_gemini_json('test-key','gemini-3.5-flash-lite','topic prompt',1.0)

        request = urlopen.call_args.args[0]
        self.assertEqual(result, {'topics':[]})
        self.assertTrue(request.full_url.startswith('https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent'))
        self.assertEqual(request.get_header('X-goog-api-key'), 'test-key')
        self.assertEqual(json.loads(request.data)['contents'][0]['parts'][0]['text'], 'topic prompt')


if __name__ == '__main__':
    unittest.main()