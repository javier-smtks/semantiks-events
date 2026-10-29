# Third-party notices

This project depends on **[trycua/cua](https://github.com/trycua/cua)** — a
cross-OS computer-use driver — as a runtime library via the `cua-driver`
Python package on PyPI. `trycua/cua` is distributed under the **MIT License**
(see `LICENSE.md` in the upstream repo).

We **do not vendor, fork, or modify** any trycua source. We call it from
`semantiks_cua.py` as a normal pip-installed dependency, which under the MIT
License only requires attribution. That attribution is this file plus the
credit paragraph in `README.md`.

For completeness, the MIT License grants are reproduced below.

```
MIT License

Copyright (c) 2025 trycua

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

Verify the exact upstream license text at:
https://github.com/trycua/cua/blob/main/LICENSE.md
