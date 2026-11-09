---
verifier:
  default_strategy: original
  strategies:
    original:
      type: script
      command: ./test.sh
---

Run the original test script from the verifier directory. The reference
loss.npz is relative to this directory and the agent output is /root/loss.npz.
