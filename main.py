import os
import re
import getpass
import sys
import tempfile
import img2pdf
import requests

from tkinter import filedialog


DEFAULT_SCALE = 4

DEFAULT_USERNAME = "<your username>"
DEFAULT_PASSWORD = "<your password>"

DEFAULT_BOOK_ID = "XXX-XXXXXXXXXX"


def input_num(prompt: str, default: int = None):
    while True:
        try:
            return int(input(prompt))
        except ValueError:
            if default is not None:
                return default


def main(temp_dir_path: str = "tmp"):
    username: str = DEFAULT_USERNAME

    if (s := input("Username (empty for default): ")) != "":
        username = s

    password: str = DEFAULT_PASSWORD

    if (s := getpass.getpass("Password (empty for default): ")) != "":
        password = s

    print("Authenticating... ", end="", flush=True)

    session = requests.Session()
    response_login_page = session.get("https://bridge.klett.de/oauth2/authorization/keycloak-ekv")

    regex = r'<form id=\"kc-form-login\"\s+onsubmit=\"login\.disabled = true; return true;\"\s+action=\"(?P<url>.*?)\"\s+method=\"post\">'
    url = re.search(regex, response_login_page.text)["url"].replace("&amp;", "&")

    request = requests.Request("POST", url)
    request.data = f"username={username}&password={password}&rememberMe=off&credentialId="
    request.cookies = response_login_page.cookies
    request.headers["Content-Type"] = "application/x-www-form-urlencoded"
    login_response = session.send(request.prepare(), allow_redirects=False)

    if login_response.status_code == 200:
        print("Wrong username or password.")
        sys.exit(1)

    login_response = session.send(login_response.next, allow_redirects=False)

    if login_response.status_code == 302:
        print("Success.")
    else:
        print("Unknown login error.")
        sys.exit(1)

    book_id: str = DEFAULT_BOOK_ID

    if (s := input("Book ID (empty for default): ")) != "":
        book_id = s

    if not session.get(f"https://bridge.klett.de/{book_id}/content/pages/page_0/Scale1.png").ok:
        print("Incorrect book ID.")
        sys.exit(1)

    print("Getting number of pages... ", end="", flush=True)

    num_pages = 0
    delta = 100

    while delta > 0:
        while session.get(f"https://bridge.klett.de/{book_id}/content/pages/page_{num_pages}/Scale1.png").ok:
            num_pages += delta

        num_pages -= delta
        delta = delta // 4

    print("Done.")

    print("Note: Page numbers are 3 behind because of the preamble")

    while (first_page := input_num("First page (empty for 0): ", 0)) > num_pages:
        pass

    while (last_page := input_num(f"Last page (empty for {num_pages}): ", num_pages)) > num_pages:
        pass

    while (scale := input_num("Image resolution (1, 2 or 4) (empty for 4): ", DEFAULT_SCALE)) not in [1, 2, 4]:
        pass

    file_name = filedialog.asksaveasfilename(
        defaultextension=".pdf",
        filetypes=[("PDF files", "*.pdf"), ("All Files", "*.*")],
        confirmoverwrite=True,
        parent=None,
        title="Chose where to save the pdf file"
    )

    if file_name == "":
        print("No file specified")
        sys.exit(1)

    image_files = []

    for page_num in range(first_page, last_page + 1):
        progress = (page_num - first_page + 1) * 100 / (last_page - first_page + 1)
        print(f"\rDownloading... ({progress:.2f}% / page {page_num})", end="", flush=True)

        address = f"https://bridge.klett.de/{book_id}/content/pages/page_{page_num}/Scale{scale}.png"
        response = session.get(address)

        if not response.ok:
            print(f"Could not get page {page_num}")
            sys.exit(1)

        image_files.append(os.path.join(temp_dir_path, f"{page_num}.png"))

        with open(image_files[-1], "wb") as tmp_file:
            tmp_file.write(response.content)

    session.close()

    print("\nMerging to pdf... ", end="", flush=True)

    with open(file_name, "wb") as pdf_file:
        pdf_file.write(img2pdf.convert(image_files))

    print("Done.")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory() as temp_dir:
        main(temp_dir)
