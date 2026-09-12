from cycling.data.models import TrainingZone, WorkoutSegment, WorkoutTemplate
from cycling.training.routine_engine import RoutineEngine


def _template() -> WorkoutTemplate:
    return WorkoutTemplate(
        name="test",
        workout_type="test",
        description="test",
        target_zone=TrainingZone.ENDURANCE,
        segments=[
            WorkoutSegment(duration_seconds=60, target_pct_ftp=50.0),
            WorkoutSegment(duration_seconds=60, target_pct_ftp=60.0),
        ],
    )


def test_pause_resume_preserves_elapsed():
    engine = RoutineEngine()
    engine.load(_template())
    engine.start()
    engine.tick(10.0, 100.0, 80.0)
    assert engine.state.total_elapsed == 10.0
    engine.pause()
    assert engine.state.status == "paused"
    engine.tick(10.0, 100.0, 80.0)
    assert engine.state.total_elapsed == 10.0
    engine.resume()
    assert engine.state.status == "playing"
    engine.tick(5.0, 100.0, 80.0)
    assert engine.state.total_elapsed == 15.0
    assert engine.state.segment_elapsed == 15.0


def test_start_resets_only_on_fresh_start():
    engine = RoutineEngine()
    engine.load(_template())
    engine.start()
    engine.tick(20.0, 100.0, 80.0)
    engine.pause()
    engine.resume()
    engine.tick(5.0, 100.0, 80.0)
    assert engine.state.total_elapsed == 25.0
    assert len(engine.state.actual_power) == 2
