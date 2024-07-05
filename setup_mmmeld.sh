#!/bin/bash

# Get the directory of the current script
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Create the mmmeld script
cat << EOF > "$SCRIPT_DIR/mmmeld"
#!/bin/bash
if [ \$# -eq 0 ]; then
    python "$SCRIPT_DIR/mmmeld.py"
else
    python "$SCRIPT_DIR/mmmeld.py" "\$@"
fi
EOF

# Make the mmmeld script executable
chmod +x "$SCRIPT_DIR/mmmeld"

# Create .local/bin if it doesn't exist
mkdir -p "$HOME/.local/bin"

# Move the mmmeld script to .local/bin
mv "$SCRIPT_DIR/mmmeld" "$HOME/.local/bin/"

# Add .local/bin to PATH if it's not already there
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.profile"
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "mmmeld has been deployed. You may need to restart your terminal or run 'source ~/.bashrc' to use it immediately."
