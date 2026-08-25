"""Run this to confirm your environment is ready. It makes one tiny API call."""
import os, sys
from dotenv import load_dotenv

load_dotenv()

print(f"Python        : {sys.version.split()[0]}")

key = os.environ.get("ANTHROPIC_API_KEY", "")
if not key or "paste-your-key" in key:
    print("ANTHROPIC_API_KEY : NOT SET")
    print("\n-> Open the file named .env and paste your key after ANTHROPIC_API_KEY=")
    sys.exit(1)
print(f"ANTHROPIC_API_KEY : set ({key[:11]}...{key[-4:]})")

import anthropic
print(f"anthropic SDK : {anthropic.__version__}")

try:
    r = anthropic.Anthropic().messages.create(
        model="claude-opus-5",
        max_tokens=1024,  # thinking shares this budget; 32 was too low
        messages=[{"role": "user", "content": "Reply with exactly: VESPER ONLINE"}],
    )
    # Opus 5 thinks by default, so content[] may start with a ThinkingBlock.
    # Always filter by block .type before reading .text.
    text = "".join(b.text for b in r.content if b.type == "text").strip()
    print(f"API call      : OK -> {text!r}  (stop_reason={r.stop_reason})")
    print(f"tokens        : in={r.usage.input_tokens} out={r.usage.output_tokens}")
    print("\nEverything is ready. We can start building.")
except anthropic.AuthenticationError:
    print("API call      : FAILED - the key was rejected. Check for typos or extra spaces.")
    sys.exit(1)
except Exception as e:
    print(f"API call      : FAILED - {type(e).__name__}: {e}")
    sys.exit(1)
