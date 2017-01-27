#!/usr/bin/env python3

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
