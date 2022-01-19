import time
from typing import Tuple

from fastapi import FastAPI, File, UploadFile
import subprocess
from pathlib import Path
import tempfile
import os
import pydantic

app = FastAPI(
    debug=False,
    title="X",
    version="0.0",
    description ="",
    terms_of_service="",
    docs_url=None,
    redoc_url=None,
    include_in_schema=False,
)


class SlicedInfo(pydantic.BaseModel):
    slicing_ok: bool = False
    print_time_sec: int = 0.0
    filament_used_g: float = 0.0
    filament_used_mm: float = 0.0


def parse_slice_info(gcode: str) -> SlicedInfo:
    info = SlicedInfo(slicing_ok=True)

    PRINT_TIME = "; estimated printing time (normal mode) = "
    FILAMENT_USED_MM = "; filament used [mm] = "
    FILAMENT_USED_G = "; total filament used [g] = "

    for line in gcode.split("\n"):
        if line.startswith(FILAMENT_USED_MM):
            info.filament_used_mm = float(line[len(FILAMENT_USED_MM):])
        if line.startswith(FILAMENT_USED_G):
            info.filament_used_g = float(line[len(FILAMENT_USED_G):])
        if line.startswith(PRINT_TIME):
            time_str = line[len(PRINT_TIME):]
            t = time.strptime(time_str, "%Mm %Ss")
            info.print_time_sec = t.tm_sec + t.tm_min*60

    return info


def do_slice(path: Path) -> Tuple[SlicedInfo, str]:
    gcode_filename = str(path) + ".gcode"
    res = subprocess.run(["prusa-slicer", str(path), "-g", "--layer-height", "0.2", "-o", gcode_filename])
    ok = res.returncode == 0

    if ok:
        with open(gcode_filename) as f:
            gcode = f.read()
            return parse_slice_info(gcode), gcode_filename

    return SlicedInfo(), ""


@app.post("/slice")
async def slice_request(file: UploadFile = File(...)):
    suffix = Path(file.filename).suffix
    print(f"suffix: {suffix}")

    if suffix not in [".stl", ".obj"]:
        return {"Error": "unsupported suffix"}

    file2store = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix) as f:
        f.write(file2store)
        print(f"saved at {f.name}")
        info, gcode_filename = do_slice(Path(f.name))
        if gcode_filename:
            os.remove(gcode_filename)
        return {"result": info, "size": len(file2store)}
