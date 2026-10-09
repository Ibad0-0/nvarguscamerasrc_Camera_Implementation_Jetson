#!/usr/bin/env python3
"""Generate a shell runner for the Jetson CAM1 camera feed."""

from __future__ import annotations

import argparse
from pathlib import Path
from textwrap import dedent


DEFAULT_OUTPUT = "run_cam1.sh"


def build_script() -> str:
    return dedent(
        """\
        #!/usr/bin/env bash
        set -euo pipefail

        # This Jetson currently exposes the physical CAM1 module as Argus index 0.
        SENSOR_ID="${SENSOR_ID:-0}"
        WIDTH="${WIDTH:-1280}"
        HEIGHT="${HEIGHT:-720}"
        FPS="${FPS:-30}"
        FLIP_METHOD="${FLIP_METHOD:-0}"
        TEST_BUFFERS="${TEST_BUFFERS:-90}"

        usage() {
          cat <<'USAGE'
        Usage: ./run_cam1.sh [--test]

        Runs the CSI camera connected as physical CAM1 using nvarguscamerasrc.

        Environment overrides:
          SENSOR_ID      Argus camera index, defaults to 0 for the detected CAM1 module
          WIDTH          Capture width, defaults to 1280
          HEIGHT         Capture height, defaults to 720
          FPS            Capture frame rate, defaults to 30
          FLIP_METHOD    nvvidconv flip-method, defaults to 0
          TEST_BUFFERS   Frame count for --test, defaults to 90

        Options:
          --test         Capture a short finite stream to fakesink instead of opening a preview
          -h, --help     Show this help
        USAGE
        }

        MODE="preview"
        case "${1:-}" in
          --test)
            MODE="test"
            shift
            ;;
          -h|--help)
            usage
            exit 0
            ;;
          "")
            ;;
          *)
            usage >&2
            exit 2
            ;;
        esac

        if [ "$#" -ne 0 ]; then
          usage >&2
          exit 2
        fi

        COMMON_PIPELINE=(
          nvarguscamerasrc sensor-id="$SENSOR_ID"
          !
          "video/x-raw(memory:NVMM),width=${WIDTH},height=${HEIGHT},framerate=${FPS}/1"
          !
          nvvidconv flip-method="$FLIP_METHOD"
        )

        if [ "$MODE" = "test" ]; then
          LOG_FILE="$(mktemp)"
          trap 'rm -f "$LOG_FILE"' EXIT

          TEST_PIPELINE=(
            nvarguscamerasrc sensor-id="$SENSOR_ID" num-buffers="$TEST_BUFFERS"
            !
            "video/x-raw(memory:NVMM),width=${WIDTH},height=${HEIGHT},framerate=${FPS}/1"
            !
            nvvidconv flip-method="$FLIP_METHOD"
            !
            fakesink sync=false
          )

          set +e
          gst-launch-1.0 -e "${TEST_PIPELINE[@]}" 2>&1 | tee "$LOG_FILE"
          GST_STATUS="${PIPESTATUS[0]}"
          set -e

          if grep -Eq 'Error generated|Invalid camera device|Failed to create CameraProvider|Done Error' "$LOG_FILE"; then
            exit 1
          fi

          exit "$GST_STATUS"
        fi

        exec gst-launch-1.0 -e "${COMMON_PIPELINE[@]}" ! nv3dsink sync=false
        """
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create the shell script that runs the CAM1 camera feed."
    )
    parser.add_argument(
        "-o",
        "--output",
        default=DEFAULT_OUTPUT,
        help=f"shell script to write, defaults to {DEFAULT_OUTPUT}",
    )
    args = parser.parse_args()

    output = Path(args.output)
    output.write_text(build_script(), encoding="utf-8")
    output.chmod(0o755)
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
