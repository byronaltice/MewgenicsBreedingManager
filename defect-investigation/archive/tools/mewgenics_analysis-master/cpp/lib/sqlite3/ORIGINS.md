Mewgenics.exe contains a fingerprint string hinting at the particular sqlite version it links:
```
Mewgenics 1.0.20870 (SHA-256 969294038979e15f1b6638ea795f9687952c62858e3f98d355f418b0f5e2f814)
141134fa0  char const data_141134fa0[0x55] = "2022-05-06 15:25:27 78d9c993d404cdfaa7fdd2973fa1052e3da9f66215cff9c5540ebe55c407d9fe", 0
```

The following amalgamation release was downloaded, then extracted into the third_party directory with no modifications:
* https://sqlite.org/2022/sqlite-amalgamation-3380500.zip

sqlite3 is dedicated to the public domain:
* https://sqlite.org/copyright.html
