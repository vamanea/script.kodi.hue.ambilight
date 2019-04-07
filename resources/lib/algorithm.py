import math
import colorsys
from colour import Color
import time

def transition_colorspace(hue, light, hsvratio):
    fullspectrum = light.fullspectrum
    h, s, v = hsvratio.hue(
        fullspectrum, hue.settings.ambilight_min, hue.settings.ambilight_max
    )
    if light.hue is None:
        light.hue = 1
    hvec = abs(h - light.hue) % int(65535/2)
    hvec = float(hvec/128.0)
    if light.sat is None:
        light.sat = 1
    svec = s - light.sat
    vvec = v - light.bri
    # changed to squares for performance
    distance = math.sqrt(hvec**2 + svec**2 + vvec**2)
    if distance > 0:
        duration = int(10 - 2.5 * distance/255)
        light.set_state(hue=h, sat=s, bri=v, transition_time=duration)

def transition_rgb(last_ratios, have_last, hsvratio, mqttc):
    h = hsvratio.h
    s = hsvratio.s
    v = hsvratio.v
    r,g,b = colorsys.hsv_to_rgb(h,s,v)
    to_color = Color(rgb=(r,g,b))
    r = int(r * 255)
    g = int(g * 255)
    b = int(b * 255)
    temperature =  str(r) + "," + str(g) + "," + str(b)

    if have_last == False:
        mqttc.publish("feeds/0001/color", temperature)
        return


    r,g,b = colorsys.hsv_to_rgb(last_ratios[0], last_ratios[1], last_ratios[2])
    from_color = Color(rgb=(r,g,b))
    hvec = abs(h - last_ratios[0]) % int(65535/2)
    hvec = float(hvec/128.0)
    svec = s - last_ratios[1]
    vvec = v - last_ratios[2]
    # changed to squares for performance
    distance = math.sqrt(hvec**2 + svec**2 + vvec**2)
    if distance > 0:
        duration = int(10 - 2.5 * distance/255)

        colors = list(from_color.range_to(to_color,20))
        for c in colors:
            r = int(c.red * 255)
            g = int(c.green * 255)
            b = int(c.blue * 255)
            temperature =  str(r) + "," + str(g) + "," + str(b)
            mqttc.publish("feeds/0001/color", temperature)
            time.sleep(duration / 50)
