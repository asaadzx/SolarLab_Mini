"""Minimal SSD1306 OLED driver for MicroPython.

Only the commands needed by this project are implemented; the driver writes the
init command sequence immediately, so a missing display raises during __init__.
"""

from micropython import const  # Define compile-time constants on MicroPython
import framebuf  # Pixel buffer used to draw text and shapes

SET_CONTRAST = const(0x81)  # Command: set display contrast
SET_ENTIRE_ON = const(0xA4)  # Command: use RAM contents for the display
SET_NORM_INV = const(0xA6)  # Command: normal (not inverted) pixel polarity
SET_DISP = const(0xAE)  # Command: display off (OR with 1 to turn on)
SET_MEM_ADDR = const(0x20)  # Command: set memory addressing mode
SET_COL_ADDR = const(0x21)  # Command: set column address range
SET_PAGE_ADDR = const(0x22)  # Command: set page address range
SET_DISP_START_LINE = const(0x40)  # Command: set display start line
SET_SEG_REMAP = const(0xA0)  # Command: remap segments horizontally
SET_MUX_RATIO = const(0xA8)  # Command: set multiplex ratio (screen height - 1)
SET_COM_OUT_DIR = const(0xC0)  # Command: set COM output scan direction
SET_DISP_OFFSET = const(0xD3)  # Command: set display offset
SET_COM_PIN_CFG = const(0xDA)  # Command: configure COM pins for the panel
SET_DISP_CLK_DIV = const(0xD5)  # Command: set display clock divide ratio
SET_PRECHARGE = const(0xD9)  # Command: set pre-charge period
SET_VCOM_DESEL = const(0xDB)  # Command: set VCOMH deselect level
SET_CHARGE_PUMP = const(0x8D)  # Command: enable or disable the charge pump


class SSD1306:
    """Drive a monochrome SSD1306 OLED over I2C using an in-memory framebuffer."""

    def __init__(self, width, height, i2c, addr=0x3c, external_vcc=False):
        """Create the framebuffer and immediately initialize the physical display."""
        self.width = width  # Display width in pixels
        self.height = height  # Display height in pixels
        self.i2c = i2c  # I2C bus used to send commands and pixels
        self.addr = addr  # I2C address of the OLED (0x3C)
        self.external_vcc = external_vcc  # True if the panel has its own supply
        self.pages = self.height // 8  # Number of 8-pixel-tall memory pages
        self.buffer = bytearray(self.pages * self.width)  # Raw pixel bytes
        self.framebuf = framebuf.FrameBuffer(  # Drawing interface over buffer
            self.buffer, self.width, self.height, framebuf.MONO_VLSB
        )
        self.init_display()  # Send setup commands; raises ENODEV if not present

    def init_display(self):
        """Send the SSD1306 power-on command sequence, then clear the screen."""
        for cmd in (  # cmd is each command byte or data byte in the sequence
            SET_DISP | 0x00,  # Turn the display off while configuring
            SET_MEM_ADDR, 0x00,  # Use horizontal addressing mode
            SET_DISP_START_LINE | 0x00,  # Start at line zero
            SET_SEG_REMAP | 0x01,  # Mirror the horizontal axis
            SET_MUX_RATIO, self.height - 1,  # Scan all rows
            SET_COM_OUT_DIR | 0x08,  # Scan COM lines bottom to top
            SET_DISP_OFFSET, 0x00,  # No vertical offset
            SET_COM_PIN_CFG, 0x02 if self.height == 32 else 0x12,  # Panel layout
            SET_DISP_CLK_DIV, 0x80,  # Default oscillator divide
            SET_PRECHARGE, 0x22 if self.external_vcc else 0xF1,  # Timing
            SET_VCOM_DESEL, 0x30,  # VCOMH level
            SET_CONTRAST, 0xFF,  # Maximum contrast
            SET_ENTIRE_ON,  # Show RAM contents
            SET_NORM_INV,  # Normal (non-inverted) colors
            SET_CHARGE_PUMP, 0x10 if self.external_vcc else 0x14,  # Pump setting
            SET_DISP | 0x01,  # Turn the display back on
        ):
            self.write_cmd(cmd)  # Send this byte as a command
        self.fill(0)  # Clear the framebuffer to black
        self.show()  # Push the cleared buffer to the display

    def write_cmd(self, cmd):
        """Send one command byte (0x80 prefix tells SSD1306 to expect a command)."""
        self.i2c.writeto(self.addr, bytearray([0x80, cmd]))  # Two-byte I2C write

    def write_data(self, buf):
        """Send a buffer of pixel bytes (0x40 prefix marks a data stream)."""
        self.i2c.writeto(self.addr, b'\x40' + buf)  # Command prefix plus pixel data

    def poweroff(self):
        """Turn the display off without changing the framebuffer."""
        self.write_cmd(SET_DISP | 0x00)  # Display-off command

    def poweron(self):
        """Turn the display back on."""
        self.write_cmd(SET_DISP | 0x01)  # Display-on command

    def contrast(self, contrast):
        """Set the display contrast level."""
        self.write_cmd(SET_CONTRAST)  # Select the contrast command
        self.write_cmd(contrast)  # Send the contrast value

    def invert(self, invert):
        """Switch between normal and inverted pixel polarity."""
        self.write_cmd(SET_NORM_INV | (invert & 1))  # Bit 0 selects inversion

    def show(self):
        """Copy the whole framebuffer to the OLED and set the write window."""
        x0 = 0  # First column for a 128-pixel-wide display
        x1 = self.width - 1  # Last column for a 128-pixel-wide display
        if self.width == 64:  # Some 64-pixel panels map to columns 32..95
            x0 = 32  # First column on 64-pixel panels
            x1 = 95  # Last column on 64-pixel panels
        self.write_cmd(SET_COL_ADDR)  # Select column-address command
        self.write_cmd(x0)  # Starting column
        self.write_cmd(x1)  # Ending column
        self.write_cmd(SET_PAGE_ADDR)  # Select page-address command
        self.write_cmd(0)  # First memory page
        self.write_cmd(self.pages - 1)  # Last memory page
        self.write_data(self.buffer)  # Stream all pixel bytes

    def fill(self, col):
        """Fill the whole framebuffer with 0 (black) or 1 (lit)."""
        self.framebuf.fill(col)  # Delegate to the framebuffer implementation

    def pixel(self, x, y, col):
        """Set or clear one pixel at (x, y)."""
        self.framebuf.pixel(x, y, col)  # x: column, y: row, col: 0 or 1

    def text(self, string, x, y, col=1):
        """Draw a text string starting at (x, y) in the given color."""
        self.framebuf.text(string, x, y, col)  # Uses the built-in 8x8 font

    def scroll(self, dx, dy):
        """Shift the framebuffer contents by dx columns and dy rows."""
        self.framebuf.scroll(dx, dy)  # Positive values scroll right/down

    def blit(self, fbuf, x, y):
        """Copy another framebuffer into this one at (x, y)."""
        self.framebuf.blit(fbuf, x, y)  # fbuf: source framebuffer object
