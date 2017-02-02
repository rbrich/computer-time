#!/usr/bin/env python3

"""
Prepare menubar icon for Computer Time app, in PDF format.

This will generate "pie clock" images for each state,
ranging from 0 to 360 degrees with step of 15 degrees.

The icon is drawn with default colors, which happens
to be black stroke on white background. This is just
fine for macOS' template icon mode.

"""

from reportlab.pdfgen import canvas


def draw_icon(filename, angle):
    c = canvas.Canvas(filename, pagesize=(36, 36))
    c.setLineWidth(2)
    if angle > 0:
        p = c.beginPath()
        p.arc(6, 6, 30, 30, 90, -angle)
        p.lineTo(18, 18)
        p.close()
        c.drawPath(p, stroke=0, fill=1)
    else:
        c.line(18, 18, 18, 30)
    c.circle(18, 18, 15)
    c.showPage()
    c.save()


if __name__ == '__main__':
    for angle in range(0, 361, 15):
        draw_icon("data/icon%03d.pdf" % angle, angle)
