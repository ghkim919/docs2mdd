# docs2mdd

[한국어](README.ko.md)

A daemon service that automatically converts documents to Markdown.

## Overview

`docs2mdd` watches a designated source directory and automatically converts document files to Markdown format, saving them to the destination directory.

```
src/                              dest/
├── report.pdf            →      ├── report/
│                                 │   ├── report.md
│                                 │   └── assets/
│                                 │       └── img_001.png
```

## Features

- [x] PDF → Markdown conversion (with image extraction)
- [x] Word (.docx) → Markdown conversion
- [x] PowerPoint (.pptx) → Markdown conversion (slide-by-slide)
- [x] Excel (.xlsx) → Markdown conversion (sheet-by-sheet tables)
- [x] Hangul (.hwpx) → Markdown conversion (Korean word processor)
- [x] HTML → Markdown conversion
- [x] **URL fetch**: Download HTML from URL and convert to Markdown
- [x] **Frontmatter metadata**: Automatically extract document metadata (title, author, dates, etc.)
- [x] Real-time file system monitoring
- [x] Directory structure preservation
- [x] Daemon mode support

## Installation

```bash
# Clone the repository
git clone https://github.com/ghkim919/docs2mdd.git
cd docs2mdd

# Install dependencies
pip install -e .

# Or install with dev dependencies
pip install -e ".[dev]"
```

## Usage

### Initial Setup

```bash
# Create config.yaml and src/, dest/ directories in current directory
docs2mdd init
```

### Running the Daemon

```bash
# Start daemon
docs2mdd start

# Run in foreground (for debugging)
docs2mdd start -f

# Check daemon status
docs2mdd status

# Stop daemon
docs2mdd stop

# Restart daemon
docs2mdd restart
```

### Single File Conversion

```bash
# Convert a single file (without daemon)
docs2mdd convert document.pdf
docs2mdd convert document.docx
docs2mdd convert document.pptx
docs2mdd convert document.xlsx
docs2mdd convert document.hwpx

# Specify output directory
docs2mdd convert document.pdf -o ./output
```

### Fetch from URL

```bash
# Download HTML from URL and convert to Markdown
docs2mdd fetch https://example.com/article.html

# Specify output directory
docs2mdd fetch https://example.com -o ./output

# Specify output filename
docs2mdd fetch https://example.com -n my_article
```

### Configuration (config.yaml)

```yaml
# Source directory (directory to watch)
src_dir: "./src"

# Destination directory (where converted files are saved)
dest_dir: "./dest"

# Supported extensions
supported_extensions:
  - ".pdf"
  - ".docx"
  - ".pptx"
  - ".xlsx"
  - ".hwpx"
  - ".html"
  - ".htm"

# Assets directory name
assets_dirname: "assets"

# Logging settings
logging:
  level: "INFO"  # DEBUG, INFO, WARNING, ERROR
  file: null     # Log file path

# Daemon settings
daemon:
  pid_file: "/tmp/docs2mdd.pid"
  poll_interval: 1.0
```

## Dependencies

- Python >= 3.9
- watchdog - File system monitoring
- PyMuPDF - PDF processing
- python-docx - Word document processing
- python-pptx - PowerPoint processing
- openpyxl - Excel processing
- beautifulsoup4 - HTML parsing
- markdownify - HTML to Markdown conversion
- PyYAML - Configuration file parsing
- click - CLI interface

## Limitations

### HWPX (Hangul) Format
- **Image extraction may not work properly**: HWPX is a proprietary format by Hancom, and the internal structure is not officially documented. Image references vary depending on the document version and creation method, so some images may not be extracted.
- **Tables are supported**, but complex merged cells may not render correctly.
- For best results, consider exporting to PDF or DOCX from Hangul before conversion.

## License

MIT License
