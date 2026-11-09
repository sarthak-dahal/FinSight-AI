from pathlib import Path
from bs4 import BeautifulSoup

data_dir = Path("data/raw/sec/microsoft/10-k")
html_file = next(data_dir.glob("*.html"))

with open(html_file, "rb") as file:
    soup = BeautifulSoup(file, "xml")

for prefix in ["item_1_", "item_1a_", "item_7_", "item_8_"]:
    print(f"\n--- {prefix} ---")

    elements = soup.find_all(
        id=lambda value: value and value.startswith(prefix)
    )

    for element in elements[:5]:
        print("ID:", element.get("id"))
        print("Tag:", element.name)
        print("Text:", element.get_text(" ", strip=True)[:300])