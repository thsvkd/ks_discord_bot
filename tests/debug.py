import pytest
import click
import os


@click.command()
@click.option('--file', '-i')
def main(file):
    args = ['-srx']
    if file:
        args.append(f'{file}')

    print(os.getcwd())

    pytest.main(args)


if __name__ == '__main__':
    main()
