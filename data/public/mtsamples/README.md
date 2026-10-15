# MTSamples local data

Put a locally obtained and authorized CSV here as `source.csv`. The preparation command accepts a CSV
header containing the required `transcription` column. An optional stable identifier may be supplied in
`id`, `sample_name`, or `sample_id`; otherwise the source row number is used. It writes at most 100 reproducibly sampled `.txt`
notes under `notes/` and a `subset.json` record. Source CSV and prepared clinical text are git-ignored.

Gold annotations, if prepared, belong in `gold/` and use the same format and span conventions as
`data/gold/`: one JSON per note stem, with `id`, `source_file`, `annotator`, and `entities` containing
`text`, `label`, `start`, and `end`. Annotate only manually reviewed notes. The downloaded dataset's
access and redistribution terms must be checked at its source; the project does not fetch it.
