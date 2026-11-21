"""doctor: повертає список перевірок у стабільному форматі (без залежності від машини)."""
import doctor


def test_checks_shape():
    rows = doctor.checks()
    assert len(rows) >= 6
    for name, need, required, hint in rows:
        assert name and need and isinstance(required, bool) and isinstance(hint, str)
    assert any("ffmpeg" in r[0] for r in rows)
