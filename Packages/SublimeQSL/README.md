SublimeQSL
==========

A sublime Text 2 package for QSL.

Currently supported features:
-----------------------------

- Syntax highlighting:
  - Basic square and angle bracket highlighting.
  - Limited number of keywords.
  - The Python syntax file is imported for LimPy blocks. There is a chance
    that non-LimPy blocks will be seen as Python code in some instances.

*Disclaimer: This is a real messy first draft experimental prototype that
             most likely has all sorts of weird highlighting going on.*

Installation
------------

Note: ``Super`` refers to either the ``CMD`` key in Mac OS X or the ``CTRL``
    key in Windows and Linux.

1. If you don't already have Package Control installed, follow these
   [installation instructions](http://wbond.net/sublime_packages/package_control/installation)
   to install it.

2. Add the channel URL:


    1. Type ``Super+SHIFT+P`` to enter the Command Prompt.
    2. Start typing ``add channel``. Once you see ``Package Control: Add Channel``
       highlighted, type ``Enter``.
    4. In the text box that has appeared at the bottom of the window,
       paste this, and type ``Enter``:

       ``https://raw.github.com/berryp/sublime_package_control_channel/master/repositories.json``

3. Install the SublimeQSL package:

    1. Type ``Super+SHIFT+P`` to enter the Command Prompt.
    2. Start typing ``install package``. Once you see ``Package Control: Install Package``
       highlighted, type ``Enter``.
    3. After a short delay, you will see available packages list. Start typing ``qsl``
       and press ``Enter`` when ``SublimeQSL`` is highlighted.

Usage
-----

To enable SublimeQSL for your files, you have two options:

1. Name your files with the ``.qsl`` extension (recommended).

2. Select ``QSL`` from the file type menu in the status bar, or in ``View > Syntax``