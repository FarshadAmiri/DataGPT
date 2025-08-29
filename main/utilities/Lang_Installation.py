import argostranslate.package
import argostranslate.translate

# from_code = "en"
# to_code = "de"

necessary_packages = {("en", "fa"), ("fa", "en"), 
                      ("en", "ar"), ("ar", "en"),
                      ("en", "he"), ("he", "en"),
                      }

# Download and install Argos Translate package
argostranslate.package.update_package_index()
available_packages = argostranslate.package.get_available_packages()

for from_code, to_code in necessary_packages:
    print(f"Downloading and installing '{from_code}' to '{to_code}' package...")
    
    package_to_install = next(filter(lambda x: x.from_code == from_code and x.to_code == to_code, available_packages))
    argostranslate.package.install_from_path(package_to_install.download())
    
    print(f"Successfully installed '{from_code}' to '{to_code}' package.\n")