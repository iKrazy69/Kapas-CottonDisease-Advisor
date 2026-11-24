# Documents the advisor answers from

The advisor answers only from the documents in this folder. The app loads every PDF, Word (.docx) and text file here when it starts and builds its search database (`chroma_data/`, created on the first start; it needs Ollama with `nomic-embed-text`).

## The CICR cotton guide (not included)

All cotton answers come from the ICAR-Central Institute for Cotton Research guide *Integrated Management of Cotton Pests, Diseases and Nematodes* (illustrative guide). It belongs to ICAR-CICR, so it is not copied into this repository. Get it from the ICAR-CICR website (https://cicr.org.in) and put it in this folder.

- **To use the app:** the PDF on its own is enough.
- **To re-run the benchmark** (`eval/`): the scripts also read a plain-text copy named `CICR_Illustrative_Guide_Cotton_Pests_Diseases_2026.txt` in this folder. The published measurements used such a copy. You can make one with `pdftotext -layout` from [Poppler](https://poppler.freedesktop.org/). A slightly different text can change which passages the search finds, so expect small differences from the published numbers.
