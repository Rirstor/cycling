from cycling.data.models import TrainingZone, WorkoutSegment, WorkoutTemplate

WORKOUT_TEMPLATES: list[WorkoutTemplate] = [
    WorkoutTemplate(
        name="endurance",
        workout_type="endurance",
        description="Steady Zone 2 endurance ride to build aerobic base and fat oxidation",
        target_zone=TrainingZone.ENDURANCE,
        segments=[
            WorkoutSegment(600, 50, description="Warm up easy"),
            WorkoutSegment(3600, 65, description="Steady endurance pace"),
            WorkoutSegment(300, 50, description="Cool down easy"),
        ],
    ),
    WorkoutTemplate(
        name="sweet_spot",
        workout_type="sweet_spot",
        description="Sustained efforts at 88-93% FTP for FTP development",
        target_zone=TrainingZone.TEMPO,
        segments=[
            WorkoutSegment(600, 50, description="Warm up"),
            WorkoutSegment(1200, 90, description="Sweet spot effort"),
            WorkoutSegment(600, 50, description="Recovery"),
            WorkoutSegment(1200, 90, description="Sweet spot effort"),
            WorkoutSegment(600, 50, description="Recovery"),
            WorkoutSegment(600, 50, description="Cool down"),
        ],
    ),
    WorkoutTemplate(
        name="threshold",
        workout_type="threshold",
        description="Classic 2x20 threshold intervals at 95-100% FTP",
        target_zone=TrainingZone.THRESHOLD,
        segments=[
            WorkoutSegment(900, 50, description="Progressive warm up"),
            WorkoutSegment(1200, 97, description="Threshold effort"),
            WorkoutSegment(600, 50, description="Recovery spin"),
            WorkoutSegment(1200, 97, description="Threshold effort"),
            WorkoutSegment(600, 50, description="Cool down"),
        ],
    ),
    WorkoutTemplate(
        name="vo2max",
        workout_type="vo2max",
        description="5x4 minute VO2 max intervals at 110-115% FTP",
        target_zone=TrainingZone.VO2MAX,
        segments=[
            WorkoutSegment(900, 50, description="Warm up"),
            WorkoutSegment(240, 112, description="VO2max effort"),
            WorkoutSegment(240, 50, description="Recovery"),
            WorkoutSegment(240, 112, description="VO2max effort"),
            WorkoutSegment(240, 50, description="Recovery"),
            WorkoutSegment(240, 112, description="VO2max effort"),
            WorkoutSegment(240, 50, description="Recovery"),
            WorkoutSegment(240, 112, description="VO2max effort"),
            WorkoutSegment(240, 50, description="Recovery"),
            WorkoutSegment(240, 112, description="VO2max effort"),
            WorkoutSegment(600, 50, description="Cool down"),
        ],
    ),
    WorkoutTemplate(
        name="anaerobic",
        workout_type="anaerobic",
        description="Short hard efforts at 130-150% FTP to build anaerobic capacity",
        target_zone=TrainingZone.ANAEROBIC,
        segments=[
            WorkoutSegment(600, 50, description="Warm up"),
            WorkoutSegment(60, 140, description="All-out sprint"),
            WorkoutSegment(120, 40, description="Active recovery"),
            WorkoutSegment(60, 140, description="All-out sprint"),
            WorkoutSegment(120, 40, description="Active recovery"),
            WorkoutSegment(60, 140, description="All-out sprint"),
            WorkoutSegment(120, 40, description="Active recovery"),
            WorkoutSegment(60, 140, description="All-out sprint"),
            WorkoutSegment(120, 40, description="Active recovery"),
            WorkoutSegment(60, 140, description="All-out sprint"),
            WorkoutSegment(600, 50, description="Cool down"),
        ],
    ),
    WorkoutTemplate(
        name="ftp_builder",
        workout_type="threshold",
        description="Progressive threshold workout to raise functional threshold power. "
        "Builds lactate tolerance with sustained near-FTP efforts.",
        target_zone=TrainingZone.THRESHOLD,
        segments=[
            WorkoutSegment(600, 50, description="Easy warm up spin"),
            WorkoutSegment(60, 60, description="Gentle spin, prepare legs"),
            WorkoutSegment(300, 70, description="Build up to moderate pace"),
            WorkoutSegment(600, 85, description="Approach sweet spot"),
            WorkoutSegment(1200, 92, description="First threshold block - hold steady pace"),
            WorkoutSegment(600, 50, description="Active recovery spin"),
            WorkoutSegment(1200, 95, description="Second threshold block - slightly harder"),
            WorkoutSegment(600, 50, description="Active recovery spin"),
            WorkoutSegment(600, 90, description="Sweet spot effort to finish"),
            WorkoutSegment(300, 50, description="Cool down easy"),
        ],
    ),
    WorkoutTemplate(
        name="vo2max_intervals",
        workout_type="vo2max",
        description="High-intensity VO2 max intervals to maximize aerobic power output. "
        "Short, hard repeats near maximal oxygen uptake.",
        target_zone=TrainingZone.VO2MAX,
        segments=[
            WorkoutSegment(600, 50, description="Easy warm up"),
            WorkoutSegment(120, 60, description="Spin lightly to prepare"),
            WorkoutSegment(180, 110, description="VO2 max effort - hold on!"),
            WorkoutSegment(180, 40, description="Active recovery, spin easy"),
            WorkoutSegment(180, 115, description="VO2 max effort - dig deep"),
            WorkoutSegment(180, 40, description="Active recovery"),
            WorkoutSegment(180, 115, description="VO2 max effort"),
            WorkoutSegment(180, 40, description="Active recovery"),
            WorkoutSegment(180, 118, description="VO2 max effort - push hard"),
            WorkoutSegment(180, 40, description="Active recovery"),
            WorkoutSegment(180, 120, description="Final VO2 max effort - give it all"),
            WorkoutSegment(600, 50, description="Cool down easy"),
        ],
    ),
]


def get_workout(name: str) -> WorkoutTemplate | None:
    for w in WORKOUT_TEMPLATES:
        if w.name == name:
            return w
    return None


def list_routines() -> list[dict]:
    result = []
    for w in WORKOUT_TEMPLATES:
        profile = []
        elapsed = 0.0
        for seg in w.segments:
            pct = seg.target_pct_ftp or 0
            profile.append([elapsed, pct])
            elapsed += seg.duration_seconds
            profile.append([elapsed, pct])
        segments_list = []
        for seg in w.segments:
            segments_list.append({
                "duration_seconds": seg.duration_seconds,
                "target_pct_ftp": seg.target_pct_ftp,
                "target_cadence_rpm": seg.target_cadence_rpm,
                "target_type": seg.target_type,
                "description": seg.description,
            })
        result.append({
            "name": w.name,
            "workout_type": w.workout_type,
            "description": w.description,
            "target_zone": w.target_zone.value,
            "target_zone_name": w.target_zone.name,
            "duration_seconds": sum(s.duration_seconds for s in w.segments),
            "segment_count": len(w.segments),
            "profile": profile,
            "segments": segments_list,
        })
    return result


def match_workout_type(time_in_zones: dict[str, float], total_seconds: float) -> str:
    if total_seconds <= 0:
        return "unknown"
    predominant = max(time_in_zones, key=time_in_zones.get)
    zone_to_type = {
        "Active Recovery": "recovery",
        "Endurance": "endurance",
        "Tempo": "sweet_spot",
        "Threshold": "threshold",
        "VO2max": "vo2max",
        "Anaerobic": "anaerobic",
        "Neuromuscular": "sprint",
    }
    return zone_to_type.get(predominant, "unknown")
