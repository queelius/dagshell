# Commands Reference

Complete list of available commands in DagShell.

## File System Navigation

| Command | Description | Example |
|---------|-------------|---------|
| `cd` | Change directory | `cd /home/user` |
| `pwd` | Print working directory | `pwd` |
| `pushd` | Push directory to stack | `pushd /tmp` |
| `popd` | Pop directory from stack | `popd` |
| `dirs` | Show directory stack | `dirs` |

## File Operations

| Command | Description | Example |
|---------|-------------|---------|
| `ls` | List directory contents | `ls -la /home` |
| `cat` | Display file contents | `cat file.txt` |
| `head` | Show first lines | `head -n 10 file.txt` |
| `tail` | Show last lines | `tail -n 10 file.txt` |
| `touch` | Create empty file | `touch newfile.txt` |
| `cp` | Copy files | `cp src.txt dst.txt` |
| `mv` | Move/rename files | `mv old.txt new.txt` |
| `rm` | Remove files | `rm -r directory/` |
| `mkdir` | Create directory | `mkdir -p path/to/dir` |

## Text Processing

| Command | Description | Example |
|---------|-------------|---------|
| `echo` | Display text | `echo "Hello"` |
| `grep` | Search patterns | `grep -i pattern file.txt` |
| `sort` | Sort lines | `sort -n numbers.txt` |
| `uniq` | Remove duplicates | `uniq -c file.txt` |
| `wc` | Word/line count | `wc -l file.txt` |
| `cut` | Extract fields | `cut -d: -f1 file.txt` |
| `tr` | Translate characters | `tr a-z A-Z` |
| `diff` | Compare files | `diff -u file1 file2` |

## File Information

| Command | Description | Example |
|---------|-------------|---------|
| `stat` | File status | `stat file.txt` |
| `du` | Disk usage | `du -h /home` |
| `find` | Find files | `find . -name "*.txt"` |

## Links

| Command | Description | Example |
|---------|-------------|---------|
| `ln` | Create links | `ln -s target link` |
| `readlink` | Read symlink | `readlink symlink` |

## Permissions

| Command | Description | Example |
|---------|-------------|---------|
| `chmod` | Change mode | `chmod 755 script.sh` |
| `chown` | Change owner | `chown user:group file` |
| `whoami` | Current user | `whoami` |
| `id` | User/group IDs | `id` |

## Path Utilities

| Command | Description | Example |
|---------|-------------|---------|
| `basename` | Strip directory | `basename /path/file.txt` |
| `dirname` | Get directory | `dirname /path/file.txt` |

## I/O Redirection

| Command | Description | Example |
|---------|-------------|---------|
| `tee` | Write to file and stdout | `ls \| tee files.txt` |
| `xargs` | Build commands | `find . \| xargs cat` |

## Environment

| Command | Description | Example |
|---------|-------------|---------|
| `env` | Show environment | `env` |
| `export` | Set variable | `export VAR=value` |

## Persistence

| Command | Description | Example |
|---------|-------------|---------|
| `save` | Save filesystem | `save backup.json` |
| `load` | Load filesystem | `load backup.json` |

## Virtual Devices

DagShell includes virtual devices:

- `/dev/null` - Discards all input
- `/dev/zero` - Produces null bytes
- `/dev/random` - Produces random bytes

```bash
echo "discard this" > /dev/null
head -c 16 /dev/random | xxd
```
