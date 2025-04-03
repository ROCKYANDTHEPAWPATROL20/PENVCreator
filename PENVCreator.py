import os
import time
import requests
import sys

# Constants
PYTHON_VERSION = "3.10.6"
PYTHON_INSTALLER = f"python-{PYTHON_VERSION}-amd64.exe"
PYTHON_URL = f"https://www.python.org/ftp/python/{PYTHON_VERSION}/{PYTHON_INSTALLER}"
PYTHON_INSTALL_PATH = r"C:\Python310" if os.name == "nt" else "/usr/local/bin/python3"


def log(message):
    print(f"[INFO] {message}")


def get_python_executable(venv_name):
    """Returns the path to the virtual environment's Python executable."""
    if os.name == "nt":
        return os.path.join(venv_name, "Scripts", "python.exe")
    else:
        return os.path.join(venv_name, "bin", "python")


def check_python():
    """Checks if Python is installed."""
    try:
        subprocess.run(["python", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        log("Python is already installed.")
        return True
    except FileNotFoundError:
        return False


def download_python():
    """Downloads Python installer."""
    log(f"Downloading {PYTHON_INSTALLER}...")
    response = requests.get(PYTHON_URL, stream=True)
    with open(PYTHON_INSTALLER, "wb") as file:
        for chunk in response.iter_content(chunk_size=1024):
            file.write(chunk)
    log("Python installer downloaded.")


def install_python():
    """Installs Python silently."""
    log("Installing Python...")
    subprocess.run([PYTHON_INSTALLER, "/quiet", "InstallAllUsers=1", "PrependPath=1",
                    f"TargetDir={PYTHON_INSTALL_PATH}"], check=True)
    os.remove(PYTHON_INSTALLER)
    log("Python installed successfully!")


def create_virtual_env(venv_name):
    """Creates a virtual environment."""
    log(f"Creating virtual environment: {venv_name}...")
    subprocess.run(["python", "-m", "venv", venv_name], check=True)
    log(f"Virtual environment '{venv_name}' created successfully.")


import subprocess
from tqdm import tqdm
import re

def is_package_installed(venv_name, package_name):
    """Checks if a package is already installed in the virtual environment."""
    python_executable = get_python_executable(venv_name)
    result = subprocess.run(
        [python_executable, "-m", "pip", "list"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    installed_packages = {line.split()[0].lower() for line in result.stdout.splitlines()[2:] if line.strip()}
    return package_name.lower() in installed_packages


def install_package(venv_name, package_name):
    """Installs a package in the virtual environment with tqdm progress updates."""
    python_executable = get_python_executable(venv_name)

    if is_package_installed(venv_name, package_name):
        log(f"ERROR: {package_name} (skipped, already installed)")
        return

    log(f"Installing: {package_name}...")

    process = subprocess.Popen(
        [python_executable, "-m", "pip", "install", package_name],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    with tqdm(desc=f"Installing {package_name}", unit="pkg", dynamic_ncols=True) as pbar:
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            match = re.search(r"Collecting (\S+)", line)
            if match:
                current_package = match.group(1)
                pbar.set_description(f"Installing: {current_package}")
                pbar.update(1)

    process.wait()

    if process.returncode == 0:
        pbar.set_description(f"Installing: {current_package} (success)")
    else:
        pbar.set_description(f"Installing: {current_package} (failed)")


def install_from_requirements(venv_name, requirements_file):
    """Installs packages from a requirements file, skipping already installed ones."""

    if not os.path.exists(requirements_file):
        log(f"ERROR: '{requirements_file}' not found.")
        return

    # Read and clean up the requirements file
    with open(requirements_file, "r") as file:
        packages = [
            re.split(r"[=<>]", line.strip())[0]  # Extract package name, ignoring version constraints
            for line in file if line.strip() and not line.startswith("#")  # Skip blank lines and comments
        ]

    if not packages:
        log("No valid packages found in requirements.txt.")
        return

    log(f"Checking for installed packages before installation...")

    python_executable = get_python_executable(venv_name)

    # Get a set of already installed packages
    result = subprocess.run(
        [python_executable, "-m", "pip", "list"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )
    installed_packages = {line.split()[0].lower() for line in result.stdout.splitlines()[2:] if line.strip()}

    to_install = [pkg for pkg in packages if pkg.lower() not in installed_packages]
    already_installed = [pkg for pkg in packages if pkg.lower() in installed_packages]

    # Log info for already installed packages
    for pkg in already_installed:
        log(f"INFO: {pkg} is already installed (skipping)")

    if not to_install:
        log("All required packages are already installed. Nothing to install.")
        return

    log(f"Installing {len(to_install)} packages from '{requirements_file}'...")

    # Install all packages in one subprocess call
    process = subprocess.Popen(
        [python_executable, "-m", "pip", "install", "-r", requirements_file],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    with tqdm(desc="Installing packages", unit="pkg", dynamic_ncols=True) as pbar:
        current_pkg = None  # Initialize package tracking
        for stdout_line in process.stdout:
            stdout_line = stdout_line.strip()
            if "Collecting" in stdout_line:
                current_pkg = stdout_line.split(' ')[1].split('[')[0].strip()
                pbar.set_description(f"Installing: {current_pkg}")
            pbar.update(1)

        process.wait()

    if process.returncode == 0:
        log("Installation process complete.")
    else:
        log("ERROR: Installation failed for some packages. Check the output for details.")

def remove_package(venv_name, package_name):
    """Removes a specific package from the virtual environment with dynamic tqdm progress bar."""
    python_executable = get_python_executable(venv_name)
    log(f"Removing package: {package_name}...")

    process = subprocess.Popen(
        [python_executable, "-m", "pip", "uninstall", "-y", package_name],
        stdout=subprocess.PIPE,  # Suppress stdout
        stderr=subprocess.PIPE,  # Suppress stderr
        text=True
    )

    # Initialize the progress bar with a single package to remove
    with tqdm(total=1, desc=f"Removing {package_name}", unit="pkg", dynamic_ncols=True) as pbar:
        for stdout_line in process.stdout:
            if "Uninstalling" in stdout_line:
                # Extract the package name from the stdout
                package_name_clean = stdout_line.split(' ')[1].split('[')[0].strip()
                pbar.set_description(f"Removing: {package_name_clean}")  # Update description dynamically
        for stderr_line in process.stderr:
            pass  # Suppress stderr

        process.wait()  # Wait for the process to finish
        pbar.update(1)  # Mark the removal as complete

    log(f"Package '{package_name}' removed successfully.")


def remove_all_packages(venv_name):
    """Removes all installed packages from the virtual environment with dynamic tqdm progress bar."""
    python_executable = get_python_executable(venv_name)
    log("Removing all installed packages...")

    # Get list of installed packages
    result = subprocess.run([python_executable, "-m", "pip", "freeze"], stdout=subprocess.PIPE, text=True)
    packages = [line.split("==")[0] for line in result.stdout.splitlines()]

    if not packages:
        log("No packages to remove.")
        return

    with tqdm(total=len(packages), desc="Removing packages", unit="pkg", dynamic_ncols=True) as pbar:
        for package in packages:
            process = subprocess.Popen(
                [python_executable, "-m", "pip", "uninstall", "-y", package],
                stdout=subprocess.PIPE,  # Suppress stdout
                stderr=subprocess.PIPE,  # Suppress stderr
                text=True
            )

            # Read the output and update the progress bar dynamically
            for stdout_line in process.stdout:
                if "Uninstalling" in stdout_line:
                    # Extract package name without extra text or brackets
                    package_name_clean = stdout_line.split(' ')[1].split('[')[0].strip()
                    pbar.set_description(f"Removing: {package_name_clean}")  # Update description dynamically
            for stderr_line in process.stderr:
                pass  # Suppress stderr

            process.wait()  # Wait for the process to finish
            pbar.update(1)  # Update the progress bar after each package removal

    log("All packages removed successfully.")


def check_for_updates(venv_name):
    """Checks for outdated packages silently and prompts the user to update them."""
    python_executable = get_python_executable(venv_name)
    log("Checking for outdated packages...")

    # Run pip list --outdated silently
    result = subprocess.run(
        [python_executable, "-m", "pip", "list", "--outdated"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,  # Suppress errors
        text=True
    )

    lines = result.stdout.splitlines()
    outdated_packages = []

    # Skip the first two lines (header), extract package names
    if len(lines) > 2:
        for line in lines[2:]:
            package_name = line.split()[0]  # Extract package name
            outdated_packages.append(package_name)

    if not outdated_packages:
        log("All packages are up to date.")
        return

    log(f"Found {len(outdated_packages)} outdated package(s).")

    choice = input("Do you want to update all outdated packages? (y/n): ").strip().lower()
    if choice == "y":
        update_packages(venv_name, outdated_packages)


def update_packages(venv_name, packages):
    """Updates outdated packages silently with tqdm progress bar and dynamic descriptions."""
    python_executable = get_python_executable(venv_name)

    with tqdm(total=len(packages), desc="Updating packages", unit="pkg", dynamic_ncols=True) as pbar:
        for package in packages:
            process = subprocess.Popen(
                [python_executable, "-m", "pip", "install", "--upgrade", package],
                stdout=subprocess.PIPE,  # Suppress stdout
                stderr=subprocess.PIPE,  # Suppress stderr
                text=True
            )

            # Read the output and update the progress bar dynamically
            for stdout_line in process.stdout:
                if "Collecting" in stdout_line:
                    # Extract package name without extra text or brackets
                    package_name_clean = stdout_line.split(' ')[1].split('[')[0].strip()
                    pbar.set_description(f"Updating: {package_name_clean}")  # Update description dynamically
            for stderr_line in process.stderr:
                pass  # Suppress stderr

            process.wait()  # Wait for the process to finish
            pbar.update(1)  # Update the progress bar after each package installation

    log("All selected packages updated successfully.")


def check_internet():
    """Checks if there is an active internet connection."""
    try:
        requests.get("https://www.google.com", timeout=5)
        return True
    except requests.ConnectionError:
        return False


def main():
    """Main function handling user interaction."""

    # Check for network connection before proceeding
    if not check_internet():
        log("ERROR: PENVCreator requires an internet connection to function.")
        log("Please check your connection and try again.")
        time.sleep(3)
        sys.exit(1)  # Exit the program

    if not check_python():
        log("Python is not installed. Downloading and installing...")
        download_python()
        install_python()

    venv_name = input("Enter the virtual environment name (default: venv): ").strip() or "venv"

    if not os.path.exists(venv_name):
        create_virtual_env(venv_name)

    check_for_updates(venv_name)

    while True:
        print("\nChoose an option:")
        print("[1] Install a package")
        print("[2] Remove a package")
        print("[3] Remove all packages")
        print("[4] Install from requirements.txt")
        print("[5] List installed packages")
        print("[6] Generate requirements.txt")
        print("[7] Check for updates")
        print("[8] Exit")
        choice = input("Enter your choice (1-8): ").strip()

        if choice == "1":
            package_name = input("Enter package name to install: ").strip()
            if package_name:
                install_package(venv_name, package_name)
        elif choice == "2":
            package_name = input("Enter package name to remove: ").strip()
            if package_name:
                remove_package(venv_name, package_name)
        elif choice == "3":
            confirm = input("Are you sure you want to remove all packages? (y/n): ").strip().lower()
            if confirm == "y":
                remove_all_packages(venv_name)
        elif choice == "4":
            requirements_file = input("Enter the path to requirements.txt: ").strip()
            if requirements_file:
                install_from_requirements(venv_name, requirements_file)
        elif choice == "5":
            python_executable = get_python_executable(venv_name)
            subprocess.run([python_executable, "-m", "pip", "list"])
        elif choice == "6":
            log("Generating requirements.txt...")
            with open("requirements.txt", "w") as req_file:
                python_executable = get_python_executable(venv_name)
                subprocess.run([python_executable, "-m", "pip", "freeze"], stdout=req_file)
            log("requirements.txt created successfully.")
        elif choice == "7":
            check_for_updates(venv_name)
        elif choice == "8":
            log("Exiting... Goodbye!")
            break
        else:
            log("Invalid choice. Please enter a number between 1 and 8.")


if __name__ == "__main__":
    main()
