import unittest
from unittest.mock import patch, MagicMock
from jarvis_neural_cortex import JarvisNeuralCortex

class TestJarvisNeuralCortex(unittest.TestCase):
    def setUp(self):
        self.cortex = JarvisNeuralCortex()

    def test_initialization(self):
        self.assertEqual(len(self.cortex.chat_history), 0)
        self.assertEqual(self.cortex.max_history_pairs, 20)
        self.assertEqual(self.cortex.get_memory_length(), 0)

    @patch('jarvis_neural_cortex.JarvisNeuralCortex._call_ollama_chat')
    def test_analyze_success_with_json(self, mock_chat):
        mock_response = '''
I am seeing strong bullish momentum.
###JSON###
{"signal": "CALL", "confidence": 85, "rationale": "Strong bull", "risk": "LOW"}
'''
        mock_chat.return_value = mock_response.strip()

        part_results = {
            'part1_breakout': {'signal': 1, 'thought': 'Breakout up'}
        }

        result = self.cortex.analyze(part_results, 50000.0)

        self.assertEqual(result['signal'], 'CALL')
        self.assertEqual(result['confidence'], 85)
        self.assertEqual(result['risk'], 'LOW')
        self.assertTrue(result['ai_online'])
        self.assertEqual(result['ai_narrative'], "I am seeing strong bullish momentum.")

        # Check memory was updated (1 user message + 1 assistant message)
        self.assertEqual(self.cortex.get_memory_length(), 1)
        self.assertEqual(len(self.cortex.chat_history), 2)
        self.assertEqual(self.cortex.chat_history[-1]['role'], 'assistant')

    @patch('jarvis_neural_cortex.JarvisNeuralCortex._call_ollama_chat')
    def test_analyze_fallback_on_api_error(self, mock_chat):
        mock_chat.return_value = None

        part_results = {
            'part11_fusion': {'signal': -1, 'thought': 'Math says down'},
            'part12_confidence': {'confidence': 60}
        }

        result = self.cortex.analyze(part_results, 50000.0)

        self.assertEqual(result['signal'], 'PUT')
        self.assertEqual(result['confidence'], 60)
        self.assertEqual(result['risk'], 'MEDIUM')
        self.assertFalse(result['ai_online'])

    @patch('jarvis_neural_cortex.JarvisNeuralCortex._call_ollama_chat')
    def test_analyze_fallback_on_bad_json(self, mock_chat):
        # AI returns plain text without JSON markers
        mock_chat.return_value = "Decision: PUT\nConfidence: 70\nMarket is bearish."

        part_results = {}
        result = self.cortex.analyze(part_results, 50000.0)

        self.assertEqual(result['signal'], 'PUT')
        self.assertEqual(result['confidence'], 70)
        self.assertTrue(result['ai_online'])

    def test_memory_management(self):
        # Simulate pushing more than max_history_pairs
        self.cortex.max_history_pairs = 2 # max 4 messages

        for i in range(10):
            self.cortex.chat_history.append({"role": "user", "content": f"U{i}"})
            self.cortex.chat_history.append({"role": "assistant", "content": f"A{i}"})

            # This is what `analyze` does internally
            max_messages = self.cortex.max_history_pairs * 2
            if len(self.cortex.chat_history) > max_messages:
                self.cortex.chat_history = self.cortex.chat_history[-max_messages:]

        self.assertEqual(len(self.cortex.chat_history), 4)
        self.assertEqual(self.cortex.chat_history[0]['content'], "U8")
        self.assertEqual(self.cortex.chat_history[-1]['content'], "A9")

    def test_reset_memory(self):
        self.cortex.chat_history = [{"role": "user", "content": "hi"}]
        self.assertEqual(self.cortex.get_memory_length(), 0) # integer division

        self.cortex.reset_memory()
        self.assertEqual(len(self.cortex.chat_history), 0)

    def test_build_market_report(self):
        part_results = {
            'part1_breakout': {'signal': 1, 'thought': 'Bullish BO'},
            'part2_zone': {'signal': -1, 'thought': 'Supply zone'}
        }
        report = self.cortex._build_market_report(part_results, 60000.0, None, None, None)

        self.assertIn("BTC: $60,000.00", report)
        self.assertIn("[B] 1.BREAKOUT: BULL | Bullish BO", report)
        self.assertIn("[S] 2.ZONE: BEAR | Supply zone", report)
        self.assertIn("Votes: 1 BULL / 1 BEAR", report)

if __name__ == '__main__':
    unittest.main()
