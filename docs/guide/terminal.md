# Terminal Emulator

DagShell includes a full terminal emulator that provides a familiar shell experience.

## Starting the Terminal

```bash
python -m dagshell.terminal
```

## Basic Navigation

```bash
# List files
ls
ls -l
ls -la /home

# Change directory
cd /home/user
cd ..
cd -         # Go to previous directory

# Print working directory
pwd

# Directory stack
pushd /tmp   # Push current dir and cd to /tmp
popd         # Pop and return to previous dir
dirs         # Show directory stack
```

## File Operations

```bash
# Create files
touch newfile.txt
echo "content" > file.txt
echo "more" >> file.txt   # Append

# Read files
cat file.txt
head -n 5 file.txt
tail -n 10 file.txt

# Copy, move, remove
cp source.txt dest.txt
mv old.txt new.txt
rm file.txt
rm -r directory/

# Create directories
mkdir newdir
mkdir -p path/to/nested/dir
```

## Text Processing

```bash
# Search
grep pattern file.txt
grep -i pattern file.txt    # Case insensitive
grep -v pattern file.txt    # Invert match

# Sort and unique
sort file.txt
sort -n numbers.txt         # Numeric sort
uniq file.txt
sort file.txt | uniq

# Word count
wc file.txt
wc -l file.txt              # Lines only

# Cut fields
cut -d: -f1 /etc/passwd
cut -d, -f1,3 data.csv

# Translate characters
echo "hello" | tr a-z A-Z
echo "hello123" | tr -d 0-9
```

## File Information

```bash
# Detailed info
stat file.txt

# Disk usage
du /home
du -h /home              # Human readable

# Compare files
diff file1.txt file2.txt
diff -u file1.txt file2.txt  # Unified format
```

## Links

```bash
# Hard link
ln target.txt link.txt

# Symbolic link
ln -s target.txt symlink.txt

# Read symlink target
readlink symlink.txt
```

## Permissions

```bash
# Change mode
chmod 755 script.sh
chmod u+x script.sh
chmod go-w file.txt

# Change owner
chown user file.txt
chown user:group file.txt

# View current user
whoami
id
```

## Piping and Redirection

```bash
# Pipe output
ls | grep txt
cat file.txt | sort | uniq

# Redirect output
ls > files.txt
ls >> files.txt          # Append

# Save and display
ls | tee files.txt
```

## Search Files

```bash
# Find files
find /home -name "*.txt"
find . -type f
find . -type d
```

## Persistence

```bash
# Save filesystem
save myfs.json

# Load filesystem
load myfs.json
```
