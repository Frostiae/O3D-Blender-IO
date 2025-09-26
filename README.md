# Blender O3D Importer and Exporter

![1758865747972](image/README/1758865747972.png "Preview")

## Introduction

Unofficial Fly For Fun model file format (.o3d) file importer and exporter for Blender. This addon handles O3D files including their skeletons, animations, materials, and more. Progress can always be made to support additional features such as bone attachments, various FlyFF utilities, or otherwise useful additions. Contributions are welcome and encouraged, and give it a star if it's something you find useful!

## Installation

Simply download the .zip file from the release section, head into Blender > Edit > Preferences > Add-ons > Install from Disk, and select the .zip file (do not extract it).

## Contribution & Development

If you have requests or suggestions, please create an issue. If you would like to contribute a feature or a fix, please start a pull request (and ideally link it to an issue).

For local development, it is recommended to use VS Code with the [Blender Development](https://marketplace.visualstudio.com/items?itemName=JacquesLucke.blender-development) extension. Once the extension is installed, open the `addons/io_o3d` folder in VS Code and use `Ctrl+Shift+P` to start Blender. You can now debug the script and it will auto-reload on save. It is also recommended to use [fake-bpy-module](https://github.com/nutti/fake-bpy-module) for Blender API autocompletion.
