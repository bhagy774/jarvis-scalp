import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

class KieGPT6Client:
    def __init__(self, api_key: str = None, base_url: str = None):
        self.api_key = (api_key or os.getenv("KIE_API_KEY", "")).strip()
        self.base_url = (base_url or os.getenv("KIE_BASE_URL", "https://api.kie.ai")).rstrip("/")
        self.endpoint = f"{self.base_url}/codex/v1/responses"

    def ask(self, prompt: str, stream: bool = False, reasoning_effort: str = "low", web_search: bool = False):
        if not self.api_key:
            raise ValueError("KIE_API_KEY missing! Set it in .env or pass to KieGPT6Client.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": "gpt-6-astra",
            "input": prompt,
            "stream": stream,
            "reasoning": {
                "effort": reasoning_effort
            }
        }

        if web_search:
            payload["tools"] = [{"type": "web_search"}]

        if stream:
            response = requests.post(self.endpoint, headers=headers, json=payload, stream=True)
            if response.status_code != 200:
                raise RuntimeError(f"Error {response.status_code}: {response.text}")
            return response.iter_lines()
        else:
            response = requests.post(self.endpoint, headers=headers, json=payload)
            if response.status_code != 200:
                raise RuntimeError(f"Error {response.status_code}: {response.text}")
            
            data = response.json()
            return self._extract_text(data), data

    def _extract_text(self, data: dict) -> str:
        """Extract readable text from response json structure"""
        try:
            if "output" in data and isinstance(data["output"], list):
                texts = []
                for item in data["output"]:
                    if "content" in item:
                        content = item["content"]
                        if isinstance(content, str):
                            texts.append(content)
                        elif isinstance(content, list):
                            for block in content:
                                if isinstance(block, dict) and "text" in block:
                                    texts.append(block["text"])
                                elif isinstance(block, str):
                                    texts.append(block)
                    elif "text" in item:
                        texts.append(item["text"])
                if texts:
                    return "\n".join(texts)
            if "choices" in data:
                return data["choices"][0]["message"]["content"]
            return json.dumps(data, indent=2, ensure_ascii=False)
        except Exception:
            return json.dumps(data, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    import sys
    if sys.stdout.encoding != 'utf-8':
        try:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    client = KieGPT6Client()
    if not client.api_key or client.api_key == "YOUR_API_KEY":
        print("[!] Please set KIE_API_KEY in C:\\jarvis\\.env")
        sys.exit(1)

    # જો કમાન્ડ લાઇન પર પ્રશ્ન આપ્યો હોય
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
        print(f"\n[તમારો પ્રશ્ન]: {prompt}\n")
        try:
            text, raw = client.ask(prompt)
            print("--- GPT-6 Astra નો જવાબ ---")
            print(text)
        except Exception as e:
            print(f"[Error] {e}")
    else:
        # Interactive Chat Mode
        print("=" * 50)
        print("  🤖 GPT-6 Astra Chat (બંધ કરવા 'exit' અથવા 'q' લખો)")
        print("=" * 50)
        while True:
            try:
                user_input = input("\nતમે > ").strip()
                if not user_input:
                    continue
                if user_input.lower() in ["exit", "quit", "q"]:
                    print("આવજો!")
                    break
                print("\n[વિચારે છે...]")
                text, raw = client.ask(user_input)
                print(f"\nGPT-6 Astra >\n{text}")
            except (KeyboardInterrupt, EOFError):
                print("\nઆવજો!")
                break
            except Exception as e:
                print(f"[Error] {e}")
