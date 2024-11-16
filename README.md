# 🍙 PimpMyRice

Creating and swapping rices made easy.

_This project is currently in alpha and may be subject to breaking changes._

https://github.com/user-attachments/assets/999c8fc1-2f67-4da5-8780-6c0e11695007


## What is a rice?

> Ricing refers to the process of customizing and optimizing the visual appearance of a desktop environment, particularly in Linux or Unix-based systems.<br />
It involves modifying elements such as themes, icons, fonts, window managers, and widgets to create a unique and aesthetically pleasing interface.<br />
A well-customized setup, called a "rice", showcases the user's attention to detail and creativity.

Take a look at [r/unixporn](https://www.reddit.com/r/unixporn) for inspiration.

## What does PimpMyRice do?

PimpMyRice allows you to generate, organize and apply your rices.<br />
It applies themes through modules, each module being responsible for styling a specific program (eg: [discord](https://github.com/pimpmyrice-modules/betterdiscord)).

## Quick start

### Install

<!-- #### Arch Linux -->
<!---->
<!-- ```bash -->
<!-- yay -S pimpmyrice-git -->
<!-- ``` -->
<!---->
<!-- #### Ubuntu -->
<!---->
<!-- ```bash -->
<!-- sudo add-apt-repository ppa:daddodev/pimpmyrice -->
<!-- sudo apt-get update -->
<!-- sudo apt-get install pimpmyrice -->
<!-- ``` -->

#### [Pipx](https://pipx.pypa.io/stable/installation/)

```bash
pipx install pimpmyrice
```

### Add some modules

[Create your own modules](https://pimpmyrice.vercel.app/docs/module#create-a-module) from scratch or clone from the [official modules](https://github.com/orgs/pimpmyrice-modules/repositories) to get started.

For example, clone the [alacritty](https://github.com/pimpmyrice-modules/alacritty) module:

```bash
pimp clone module pimp://alacritty
```

### Generate and apply a new theme

Generate a theme from an image:

```bash
pimp gen Downloads/example.png
# or
pimp gen https://website.com/example.png
```

Set the generated theme:

```bash
pimp set theme example
```

## [Documentation](https://pimpmyrice.vercel.app/docs)
