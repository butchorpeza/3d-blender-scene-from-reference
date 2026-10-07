import sys
from PIL import Image, ImageChops, ImageFilter, ImageOps
src, dst = sys.argv[1], sys.argv[2]
im = Image.open(src).convert('RGB')
w, h = im.size
# bloom from bright areas
hi = im.point(lambda v: max(0, v - 205) * 5 if v > 205 else 0)
bl = hi.filter(ImageFilter.GaussianBlur(w * 0.010)).point(lambda v: int(v * 0.30))
bl2 = hi.filter(ImageFilter.GaussianBlur(w * 0.035)).point(lambda v: int(v * 0.22))
out = ImageChops.screen(ImageChops.screen(im, bl), bl2)
# vignette
g = Image.radial_gradient('L').resize((w, h), Image.BICUBIC)
vig = g.point(lambda v: int(255 - max(0, v - 90) * 0.17))
out = ImageChops.multiply(out, Image.merge('RGB', (vig, vig, vig)))
# fine film grain
n = Image.effect_noise((w, h), 3.2).convert('RGB')
out = ImageChops.add(out, n, 1.0, -128)
out.save(dst)
print('post ok', dst)
