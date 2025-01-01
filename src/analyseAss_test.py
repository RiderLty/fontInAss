from pathlib import Path

from viztracer import VizTracer  # type: ignore

from analyseAss import analyseAss

subtitles: list[str] = []
for path in (Path(__file__).parent.parent / "test").iterdir():
    print(path)
    subtitles.append(path.read_text(encoding="utf-8"))

with VizTracer() as tracer:
    for subtitle in subtitles:
        analyseAss(subtitle)
