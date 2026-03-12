import os

filepath = r'\\nas.local\Documents\prism\ui\dashboard.py'
with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if line.startswith('from ui.button_edit_widget import ButtonEditWidget'):
        new_lines.append(line)
        new_lines.append('from ui.visuals.dashboard_effects import (\n    draw_aurora_border, draw_rainbow_border, draw_prism_shard_border,\n    draw_liquid_mercury_border, capture_glass_background\n)\n')
        continue

    if line.strip() == 'if self.border_anim.state() == QPropertyAnimation.State.Running:':
        new_lines.append(line)
        new_lines.append('            rect = QRectF(self.container.geometry()).adjusted(0, 0, 0, 0)\n')
        new_lines.append('            if self._border_effect == \'Rainbow\':\n')
        new_lines.append('                draw_rainbow_border(painter, rect, self._border_progress)\n')
        new_lines.append('            elif self._border_effect == \'Aurora Borealis\':\n')
        new_lines.append('                draw_aurora_border(painter, rect, self._border_progress)\n')
        new_lines.append('            elif self._border_effect == \'Prism Shard\':\n')
        new_lines.append('                draw_prism_shard_border(painter, rect, self._border_progress)\n')
        new_lines.append('            elif self._border_effect == \'Liquid Mercury\':\n')
        new_lines.append('                draw_liquid_mercury_border(painter, rect, self._border_progress)\n')
        skip = True
        continue
    
    if skip and line.strip().startswith('def _on_dimmer_requested('):
        skip = False
        new_lines.append(line)
        continue
        
    if skip:
        continue
        
    if line.strip().startswith('def _capture_glass_background('):
        skip = True
        continue
        
    if skip and line.strip().startswith('def show_near_tray('):
        skip = False
        new_lines.append(line)
        continue
        
    if skip:
        continue
        
    if 'self._capture_glass_background()' in line:
        new_lines.append(line.replace('self._capture_glass_background()', 'self._glass_bg_pixmap, self._glass_capture_pos = capture_glass_background(self)'))
        continue

    new_lines.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('Updated dashboard.py successfully')
