"""Educational grayscale denoiser, not a hardware ISP model."""
import json
from pathlib import Path
import sys


def read_pgm(path):
    tokens = Path(path).read_text(encoding='ascii').split()
    if len(tokens) < 4 or tokens[0] != 'P2' or tokens[3] != '255':
        raise ValueError('Demo accepts P2 PGM maxval 255 without comments')
    w, h = int(tokens[1]), int(tokens[2])
    pixels = [int(v) for v in tokens[4:]]
    if w <= 0 or h <= 0 or len(pixels) != w*h or any(not 0 <= x <= 255 for x in pixels):
        raise ValueError('Invalid PGM')
    return w, h, pixels


def write_pgm(path, w, h, pixels):
    Path(path).write_text(f'P2\n{w} {h}\n255\n' + '\n'.join(' '.join(str(x) for x in pixels[y*w:(y+1)*w]) for y in range(h)) + '\n', encoding='ascii')


def weight(gain):
    return max(0.0, min(1.0, (gain-4)/4, (24-gain)/8))


def process(w, h, pixels, strength):
    result = []
    for y in range(h):
        for x in range(w):
            values = [pixels[yy*w+xx] for yy in range(max(0,y-1), min(h,y+2)) for xx in range(max(0,x-1), min(w,x+2))]
            result.append(max(0, min(255, round(pixels[y*w+x]*(1-strength)+sum(values)/len(values)*strength))))
    return result


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    strength = float(job['tuning']['modules']['DENOISE']['regions']['HIGH']['parameters']['strength'])
    if not 0 <= strength <= 1:
        raise ValueError('strength must be in [0,1]')
    artifacts = {}
    for index, frame in enumerate(job['frames']):
        w, h, pixels = read_pgm(frame['path'])
        gain = float(frame.get('processing_gain') or frame['gain'])
        output = Path(job['output_dir']) / f'frame_{index:06}.pgm'
        write_pgm(output, w, h, process(w, h, pixels, strength*weight(gain)))
        artifacts[frame['id']] = str(output)
    Path(job['result_path']).write_text(json.dumps({'artifacts': artifacts}), encoding='utf-8')


if __name__ == '__main__':
    main()
