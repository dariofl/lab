#!/usr/bin/python3
import sys
import argparse
import os
from collections import Counter, deque
from multiprocessing import Pipe, Process


def get_header_data(ppm_file):
    data_header = {
        'magic_number': None,
        'width': 0,
        'height': 0,
        'max_color': 0,
        'valid': False,
        'position': 0
    }

    magic_number = ppm_file.readline().strip().decode()

    if magic_number in ('P3', 'P6'):
        data_header['magic_number'] = magic_number

    while True:
        line = ppm_file.readline().strip().decode()
        if line.startswith('#'):
            continue
        if len(line.split()) == 2:
            data_header['width'] = int(line.split()[0])
            data_header['height'] = int(line.split()[1])
            continue
        if data_header.get('width') == 0:
            data_header['width'] = line
            continue
        if data_header.get('height') == 0:
            data_header['height'] = line
            continue
        if data_header.get('max_color') == 0:
            data_header['max_color'] = line
            data_header['position'] = 1
            break

    if data_header.get('magic_number') is not None and data_header.get('width') != 0 \
            and data_header.get('height') != 0 and data_header.get('max_color') != 0 \
            and data_header.get('magic_number') != 0:
        data_header['valid'] = True
    return data_header


def create_header_ppm(data):
    header = data.get('magic_number') + '\n'
    header += str(data.get('width')) + ' ' + str(data.get('height')) + '\n'
    header += str(data.get('max_color')) + '\n'
    return header


def get_rgb_position(color):
    position = 0
    if color == 'green':
        position = 1
    elif color == 'blue':
        position = 2

    return position


def create_ppm_p6(color, file_path, color_values):
    with open(file_path, 'rb') as f:
        header_data = get_header_data(f)
    f.close()

    header_ppm = create_header_ppm(header_data)

    count_size = header_data.get('width') * header_data.get('height')
    data = []
    for i in range(count_size):
        data.append((0, 0, 0))

    position = get_rgb_position(color)

    rgb = [list(data[i]) for i in range(0, len(data), 1)]

    for i, x in enumerate(rgb):
        for index in range(len(x)):
            if index == position:
                x[index] = int(color_values[i])
    rgb_filtered = [item for sublist in rgb for item in sublist]

    if rgb_filtered and header_ppm:
        filename = file_path.split('.')[0]
        filename_color = color[0] + '_' + filename + '.ppm'
        with open(filename_color, 'wb') as f:
            f.write(bytes(header_ppm.encode()))
            f.write(bytes(rgb_filtered))
        f.close()


def parse_color(child_pipe, color, file_path):
    original_name_ppm = file_path.split('.')[0]
    filename = color[0] + '_' + original_name_ppm + '.txt'

    values = []
    while child_pipe.poll():
        value = child_pipe.recv()
        if isinstance(value, bytes):
            concatenate_values = '\n'.join(str(x) for x in value)
        else:
            concatenate_values = '\n'.join(list(x.decode() for x in value))
        values.append(concatenate_values)
        values.append('\n')

    child_pipe.close()

    with open(filename, 'w+') as f:
        color_values = ''.join(values).split()
        count_lines = Counter(color_values)
        f.write('{0}\tcount\n'.format(color))
        for x in count_lines:
            f.write("{0}\t{1}\n".format(x, count_lines[x]))

    f.close()

    create_ppm_p6(color, file_path, color_values)


if __name__ == '__main__':

    parser = argparse.ArgumentParser(description='TP 1')

    parser.add_argument('-s', '--size', dest="size", required=True, type=int, metavar='bloque de lectura',
                        help='Ingrese cantidad de bytes a leer.')
    parser.add_argument('-f', '--file', action="store", dest="ppm_file", metavar='archivo ppm', type=str,
                        required=True, help="Nombre del archivo PPM")

    options = parser.parse_args()

    header_read = False
    remove_header = True
    init_process = True
    rgb_position = deque('rgb')

    # creamos pipes rgb
    parent_red_pipe, child_red_pipe = Pipe()
    parent_green_pipe, child_green_pipe = Pipe()
    parent_blue_pipe, child_blue_pipe = Pipe()

    # creamos procesos
    red_process = Process(target=parse_color, args=(child_red_pipe, 'red', options.ppm_file))
    green_process = Process(target=parse_color, args=(child_green_pipe, 'green', options.ppm_file))
    blue_process = Process(target=parse_color, args=(child_blue_pipe, 'blue', options.ppm_file))
    header_data = None
    with open(options.ppm_file, 'rb') as f:
        while True:
            if not header_read:
                header_data = get_header_data(f)
                if not header_data.get('valid'):
                    os.write(1, b'Error al leer la cabecera\n')
                    break
                header_read = True

            if header_read and init_process:
                init_process = False
                # iniciamos procesos
                red_process.start()
                green_process.start()
                blue_process.start()

                # cerramos pipes hijo
                child_red_pipe.close()
                child_green_pipe.close()
                child_blue_pipe.close()

            ppm_block_data = f.read(options.size)
            # data = ppm_block_data.splitlines()

            block_data = ppm_block_data

            if header_data.get('magic_number') == 'P3':
                block_data = block_data.split()

            # rgb = [tuple(block_data[i:i + 3]) for i in range(0, len(block_data), 3)]

            red_index = next((idx for idx, val in enumerate(rgb_position) if val == 'r'), None)
            green_index = next((idx for idx, val in enumerate(rgb_position) if val == 'g'), None)
            blue_index = next((idx for idx, val in enumerate(rgb_position) if val == 'b'), None)
            red = block_data[red_index::3]

            green = block_data[green_index::3]
            blue = block_data[blue_index::3]

            parent_red_pipe.send(red)
            parent_green_pipe.send(green)
            parent_blue_pipe.send(blue)

            if len(block_data) % 3 == 1:
                rgb_position.rotate(-1)

            elif len(block_data) % 3 == 2:
                rgb_position.rotate(-2)

            if len(ppm_block_data) != options.size:
                parent_red_pipe.close()
                parent_green_pipe.close()
                parent_blue_pipe.close()

                red_process.join()
                green_process.join()
                blue_process.join()

                os.write(1, b'Termimaron los hijos\n')
                break

            else:
                if remove_header:
                    remove_header = False

    f.close()
    sys.exit()
