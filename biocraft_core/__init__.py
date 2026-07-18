# biocraft_core — Core runtime for Biocraft-Spark.
#
# Standard container paths that every plugin step must use:
#   INPUT_DIR   — where upstream outputs are mounted for this step to read
#   OUTPUT_DIR  — where this step writes its results
#   SHARED_DIR  — pipeline-wide shared workspace (reference genomes, etc.)
#
# Plugin developers: your container command should read from INPUT_DIR
# and write to OUTPUT_DIR.  Biocraft handles the routing between steps.

INPUT_DIR = "/data/input"
OUTPUT_DIR = "/data/output"
SHARED_DIR = "/data/shared"
