echo AUTOGEN_TESTBED_SETTING: [$AUTOGEN_TESTBED_SETTING]

# Speed optimisation for native (non-Docker) runs:
# Agbench creates a fresh .agbench_venv per instance, but in native mode
# all dependencies are already installed in the shared venv.
# Reactivate the shared venv so `pip install -r requirements.txt` is instant.
SHARED_VENV="/home/atemin/autogen/.venv"
if [ "$AUTOGEN_TESTBED_SETTING" = "Native" ] && [ -f "$SHARED_VENV/bin/activate" ]; then
    deactivate 2>/dev/null || true
    . "$SHARED_VENV/bin/activate"
    echo "Using shared venv: $SHARED_VENV (pip install will be a no-op)"
fi
