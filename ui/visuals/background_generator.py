import random
from PyQt6.QtCore import Qt, QPointF, QRectF, QPoint
from PyQt6.QtGui import (
    QColor, QPainter, QPixmap, QLinearGradient, QRadialGradient, 
    QBrush, QPen, QPainterPath, QConicalGradient
)

class BackgroundGenerator:
    """
    Generates procedural abstract backgrounds with frosted glass effects.
    Designed for media player placeholders.
    """
    
    # Modern, aesthetic palettes (fallback)
    PALETTES = [
        ["#4e54c8", "#8f94fb"], # Retro wave
        ["#11998e", "#38ef7d"], # Moss
        ["#FC466B", "#3F5EFB"], # Sunset
        ["#C6FFDD", "#FBD786", "#f7797d"], # Beach
        ["#12c2e9", "#c471ed", "#f64f59"], # Synth
        ["#2980B9", "#6DD5FA", "#FFFFFF"], # Ice
        ["#8E2DE2", "#4A00E0"], # Purple
        ["#00b09b", "#96c93d"], # Greenish
        ["#D3CCE3", "#E9E4F0"], # Muted White
        ["#20002c", "#cbb4d4"], # Dark Purple
    ]

    @staticmethod
    def generate(width: int, height: int, seed: int = None, palette: list[str] = None) -> QPixmap:
        """
        Generate a random background pixmap.
        
        Args:
            width: Width of the background.
            height: Height of the background.
            seed: Random seed for deterministic generation.
            palette: Optional list of hex color strings or QColors.
        
        Returns:
            QPixmap: The generated background.
        """
        # Ensure minimum size to avoid errors
        width = max(1, width)
        height = max(1, height)
        
        # Initialize random generator
        if seed is None:
            seed = random.randint(0, 1000000)
        
        rng = random.Random(seed)
        
        # 1. Setup Canvas
        pixmap = QPixmap(width, height)
        # Fill with a base color (usually dark for modern look)
        pixmap.fill(QColor("#1a1a1a"))
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 2. Resolve Palette
        if not palette:
            palette = rng.choice(BackgroundGenerator.PALETTES)
        
        # Convert to QColors if strings
        q_palette = [QColor(c) if isinstance(c, str) else c for c in palette]
        
        # 3. Draw Background Gradient (Base)
        grad_type = rng.choice(['linear', 'radial', 'conical'])
        
        if grad_type == 'linear':
            # Random angle
            start = QPointF(0, 0)
            end = QPointF(width, height)
            if rng.random() > 0.5:
                start = QPointF(width, 0)
                end = QPointF(0, height)
            
            grad = QLinearGradient(start, end)
            
        elif grad_type == 'radial':
            center = QPointF(width * rng.random(), height * rng.random())
            radius = max(width, height) * (0.5 + rng.random())
            grad = QRadialGradient(center, radius)
            
        else: # conical
            center = QPointF(width/2, height/2)
            angle = rng.random() * 360
            grad = QConicalGradient(center, angle)
            
        # Apply palette to gradient
        if len(q_palette) == 1:
            grad.setColorAt(0, q_palette[0].darker(150))
            grad.setColorAt(1, q_palette[0])
        else:
            for i, color in enumerate(q_palette):
                pos = i / (len(q_palette) - 1)
                grad.setColorAt(pos, color)
                
        painter.fillRect(0, 0, width, height, grad)
        
        # 4. Draw Layers (Shapes)
        num_layers = rng.randint(2, 5)
        
        for _ in range(num_layers):
            BackgroundGenerator._draw_random_layer(painter, width, height, rng, q_palette)
            
        painter.end()
        
        # 5. Apply Effects (Frosted Glass / Noise)
        final_pixmap = BackgroundGenerator._apply_frosted_effect(pixmap, rng)
        
        return final_pixmap
    
    @staticmethod
    def _draw_random_layer(painter: QPainter, w: int, h: int, rng: random.Random, palette: list[QColor]):
        """Draws a single layer of random shapes."""
        shape_type = rng.choice(['circles', 'stripes', 'blobs', 'rects', 'dots'])
        
        # Pick a random color from palette
        base_color = rng.choice(palette)
        # Randomize alpha for layering
        color = QColor(base_color)
        color.setAlpha(rng.randint(30, 150))
        
        # Blend mode? (Qt Painter composition modes)
        # Some modes look cool, others break things. Let's stick to SourceOver or Overlay-ish logic via alpha.
        # painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver) 
        
        pen = QPen(Qt.PenStyle.NoPen)
        painter.setPen(pen)
        painter.setBrush(QBrush(color))
        
        if shape_type == 'circles':
            # Scatter random circles
            count = rng.randint(3, 10)
            for _ in range(count):
                r = rng.randint(20, min(w, h) // 2)
                cx = rng.randint(-r, w + r)
                cy = rng.randint(-r, h + r)
                painter.drawEllipse(QPointF(cx, cy), r, r)
                
        elif shape_type == 'stripes':
            # Draw diagonal stripes
            thickness = rng.randint(10, 50)
            spacing = thickness * 2
            angle = rng.randint(-45, 45)
            
            painter.save()
            painter.translate(w/2, h/2)
            painter.rotate(angle)
            painter.translate(-w, -h) # Move back far enough to cover rotation
            
            # Draw enough stripes to cover
            limit = max(w, h) * 3
            for x in range(0, limit, spacing):
                painter.drawRect(x, -limit, thickness, limit * 2)
                
            painter.restore()
            
        elif shape_type == 'rects':
            # Rounded rects
            count = rng.randint(3, 8)
            for _ in range(count):
                rw = rng.randint(50, 200)
                rh = rng.randint(50, 200)
                rx = rng.randint(-50, w)
                ry = rng.randint(-50, h)
                rot = rng.randint(0, 360)
                
                painter.save()
                painter.translate(rx + rw/2, ry + rh/2)
                painter.rotate(rot)
                painter.drawRoundedRect(QRectF(-rw/2, -rh/2, rw, rh), 20, 20)
                painter.restore()
        
        elif shape_type == 'dots':
             # Grid of dots
             size = rng.randint(4, 15)
             gap = rng.randint(20, 50)
             offset_x = rng.randint(0, gap)
             offset_y = rng.randint(0, gap)
             
             for y in range(0, h, gap):
                 for x in range(0, w, gap):
                     painter.drawEllipse(QPointF(x + offset_x, y + offset_y), size/2, size/2)
                     
        elif shape_type == 'blobs':
            # Random curves (simple approximation)
            path = QPainterPath()
            sx, sy = rng.randint(0, w), rng.randint(0, h)
            path.moveTo(sx, sy)
            
            for _ in range(3):
                px1 = rng.randint(-w//2, int(w*1.5))
                py1 = rng.randint(-h//2, int(h*1.5))
                px2 = rng.randint(-w//2, int(w*1.5))
                py2 = rng.randint(-h//2, int(h*1.5))
                ex = rng.randint(0, w)
                ey = rng.randint(0, h)
                path.cubicTo(px1, py1, px2, py2, ex, ey)
                
            path.closeSubpath()
            painter.drawPath(path)

    @staticmethod
    def _apply_frosted_effect(source: QPixmap, rng: random.Random) -> QPixmap:
        """Applies blur and noise to create a frosted glass aesthetic."""
        
        # 1. Downscale -> Upscale Blur
        # This is strictly faster than a full Gaussian kernel on the CPU
        orig_size = source.size()
        w, h = orig_size.width(), orig_size.height()
        
        # Downscale factor (smaller = more blur)
        scale_factor = 0.1
        small_w = max(1, int(w * scale_factor))
        small_h = max(1, int(h * scale_factor))
        
        small = source.scaled(
            small_w, small_h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        blurred = small.scaled(
            w, h,
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        
        # 2. Add White/Noise Overlay
        painter = QPainter(blurred)
        
        # White tint for "frost"
        painter.fillRect(0, 0, w, h, QColor(255, 255, 255, 20))
        
        # Noise (Optional, adds texture)
        # We can draw random pixels or a pre-calculated noise pattern.
        # Since we want speed, we won't iterate pixels in Python.
        # Instead, we just trust the blur + shapes are enough texture.
        # Or, we can draw a few thousand tiny random points? (Might be slow)
        # SKIP pixel-level noise for performance.
        
        painter.end()
        
        return blurred
