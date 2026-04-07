"""Tests for ReferenceImage data model."""
import pytest
from PIL import Image
from src.reference_image import ReferenceImage


class TestReferenceImage:
    def test_default_values(self):
        img = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        ref = ReferenceImage(image=img)
        assert ref.x == 0
        assert ref.y == 0
        assert ref.scale == 1.0
        assert ref.opacity == 0.3
        assert ref.visible is True
        assert ref.path == ""
        assert ref.image.size == (10, 10)

    def test_custom_values(self):
        img = Image.new("RGBA", (20, 15), (0, 255, 0, 255))
        ref = ReferenceImage(image=img, x=5, y=10, scale=0.5,
                             opacity=0.7, visible=False, path="/tmp/test.png")
        assert ref.x == 5
        assert ref.y == 10
        assert ref.scale == 0.5
        assert ref.opacity == 0.7
        assert ref.visible is False
        assert ref.path == "/tmp/test.png"

    def test_fit_to_canvas(self):
        """fit_to_canvas should calculate scale so image fits within bounds."""
        img = Image.new("RGBA", (100, 50))
        ref = ReferenceImage(image=img)
        ref.fit_to_canvas(50, 50)
        assert ref.scale == 0.5
        assert ref.x == 0
        assert ref.y == 0

    def test_fit_to_canvas_tall_image(self):
        """Tall image should scale based on height."""
        img = Image.new("RGBA", (20, 100))
        ref = ReferenceImage(image=img)
        ref.fit_to_canvas(40, 40)
        assert ref.scale == pytest.approx(0.4)

    def test_fit_to_canvas_smaller_image(self):
        """Image smaller than canvas should scale to 1.0 (no upscale)."""
        img = Image.new("RGBA", (10, 10))
        ref = ReferenceImage(image=img)
        ref.fit_to_canvas(50, 50)
        assert ref.scale == 1.0
