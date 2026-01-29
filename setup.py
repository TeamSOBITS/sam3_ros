import os
from glob import glob
from setuptools import setup

package_name = 'sam3_ros'

setup(
    name=package_name,
    version='1.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        (os.path.join('share', package_name, 'weights'), glob('weights/*')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Sim Jiahao',
    maintainer_email='simjiahao9@gmail.com',
    description='SAM 3 for ROS 2',
    license='BSD-3-Clause',
    entry_points={
        'console_scripts': [
            'sam3_node = sam3_ros.sam3_node:main',
        ],
    },
)
