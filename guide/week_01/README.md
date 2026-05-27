# Week 1: Linux/Unix Fundamentals

**Month 1: Foundations | Days 1–6**

Before touching email systems or writing code, every engineer must be comfortable in the Linux environment. This week builds command-line fluency, shell scripting basics, and text processing skills — all essential for operating Postfix, Dovecot, and the ifinmail App platform.

---

## Learning Goals for the Week

By Sunday, you will be able to:

- Navigate the Linux file system and manipulate files/directories from the terminal
- Understand and manage file permissions, users, and groups
- Monitor and manage processes
- Write basic shell scripts with variables, conditionals, and loops
- Process text with `grep`, `sed`, `awk`, `cut`, and `sort`
- Use `systemd` to manage services (critical for Postfix/Dovecot later)
- SSH into a remote machine and work confidently

---

## Day 1 (Monday): The Terminal & File System

### Learning Objectives
- Understand what a shell is and how the terminal works
- Navigate the file system with `cd`, `ls`, `pwd`
- Create, move, copy, and delete files and directories
- Understand the Linux directory hierarchy (`/etc`, `/var`, `/home`, `/tmp`)

### Theory / Reading
- **The Unix Shell**: bash, zsh, fish — we standardize on bash for server work
- **File system hierarchy**: `/` (root), `/etc` (configuration), `/var` (variable data like logs and mail spools), `/home` (user directories), `/tmp` (temporary files)
- **Paths**: absolute (`/etc/postfix/main.cf`) vs relative (`../../var/log`)
- **Hidden files**: everything starting with `.` is hidden by default

### Practical Exercise
```bash
# Explore the file system
ls /                    # What lives at root?
ls -la /etc             # List all files (including hidden) in /etc
pwd                     # Where am I?
cd /var && pwd          # Navigate and confirm
cd ~ && pwd             # Go home

# Create and manipulate files
mkdir -p ~/ifinmail-tmp/subdir
touch ~/ifinmail-tmp/hello.txt
echo "ifinmail week 1" > ~/ifinmail-tmp/hello.txt
cat ~/ifinmail-tmp/hello.txt
cp ~/ifinmail-tmp/hello.txt ~/ifinmail-tmp/backup.txt
mv ~/ifinmail-tmp/backup.txt ~/ifinmail-tmp/renamed.txt
rm ~/ifinmail-tmp/renamed.txt

# Clean up
rm -rf ~/ifinmail-tmp
```

### Checkpoint Questions
1. What is the difference between `cd /etc` and `cd etc`?
2. Where would you expect to find Postfix configuration files? (Hint: read the proposal)
3. What does `ls -la` show that `ls` does not?
4. Why is `/var` important for a mail server?

### Connection to ifinmail App
Postfix stores its configuration in `/etc/postfix/`. Mail queues live in `/var/spool/postfix/`. Dovecot stores mail in `/var/mail/` or `/var/vmail/`. Everything in this week maps directly to the directories you will work with when setting up the mail stack.

---

## Day 2 (Tuesday): File Permissions, Users & Groups

### Learning Objectives
- Read and interpret Linux file permissions (`rwxr-xr--`)
- Change permissions with `chmod` and ownership with `chown`
- Understand users, groups, and `sudo`
- Know why mail services run as their own users

### Theory / Reading
- **Permission triplets**: owner / group / others, each with read (r), write (w), execute (x)
- **Numeric notation**: `644` = rw-r--r--, `755` = rwxr-xr-x, `600` = rw-------
- **Service accounts**: Postfix runs as `postfix`, Dovecot as `dovecot` — never as root
- **sudo**: execute commands as another user (typically root)

### Practical Exercise
```bash
# Inspect permissions
ls -la /etc/postfix/   # If Postfix is not installed, try /etc/ instead
stat /etc/passwd

# Create files with different permissions
echo "secret key" > ~/secret.txt
chmod 600 ~/secret.txt     # Only owner can read/write
ls -la ~/secret.txt
chmod 644 ~/secret.txt     # Owner read/write, others read-only
ls -la ~/secret.txt

# Explore users and groups
cat /etc/passwd | head -5   # System users
cat /etc/group | head -5    # System groups
whoami                       # Who am I?
groups                       # What groups am I in?
id                           # All identity info

# Observe service users (if they exist)
id postfix 2>/dev/null || echo "postfix user not created yet — we will create it in Week 5"
id dovecot 2>/dev/null || echo "dovecot user not created yet — we will create it in Week 6"
```

### Checkpoint Questions
1. Why should Postfix and Dovecot run as their own users instead of root?
2. What does `chmod 640 main.cf` mean? Who can read? Who can write?
3. If a file has permissions `---------T`, what happened? (Hint: sticky bit)
4. Why might `/etc/postfix/` be owned by root but readable by group `postfix`?

### Connection to ifinmail App
Mail services must be isolated. Postfix's `master.cf` defines which user each service runs as. DKIM private keys must be `600` (owner-only readable). Misconfigured permissions on mail spools or TLS certificates are security incidents.

---

## Day 3 (Wednesday): Processes & Process Management

### Learning Objectives
- List and monitor running processes
- Understand process states (running, sleeping, zombie)
- Send signals to processes (`kill`, `SIGTERM`, `SIGHUP`)
- Understand foreground vs background vs daemon processes

### Theory / Reading
- **Process**: a running instance of a program, with a PID (process ID) and PPID (parent PID)
- **Daemon**: a background process that runs continuously (Postfix, Dovecot, nginx)
- **Signals**: `SIGTERM` (15, polite stop), `SIGKILL` (9, force stop), `SIGHUP` (1, reload config)
- **systemd**: the init system that starts/stops/manages services on modern Linux

### Practical Exercise
```bash
# List processes
ps aux | head -20          # All processes, first 20
ps aux | grep systemd      # Find systemd processes
top -n 1 | head -10        # Snapshot of top resource users

# Create and manage a background process
sleep 300 &                 # Start a long sleep in background
jobs                        # List background jobs
kill %1                     # Terminate it (or use its PID)

# Explore systemd (the service manager)
systemctl list-units --type=service | head -20
systemctl status sshd       # Check SSH daemon status (may be 'ssh' on some systems)
journalctl -n 20            # Last 20 log lines

# Find processes by name
pgrep -a systemd
pidof systemd
```

### Checkpoint Questions
1. What is the difference between `SIGTERM` and `SIGKILL`? When would you use each?
2. What does `systemctl reload postfix` do differently from `systemctl restart postfix`?
3. Why do mail servers run as daemons rather than foreground processes?
4. How would you check if Postfix is running?

### Connection to ifinmail App
Every mail component (Postfix, Dovecot, Rspamd) runs as a systemd service. When we configure these in Weeks 5-7, you will use `systemctl start/enable/status/reload` constantly. Understanding processes is essential for debugging delivery issues.

---

## Day 4 (Thursday): Shell Scripting Basics

### Learning Objectives
- Write and execute a shell script
- Use variables, command substitution, and quoting
- Write conditionals (`if`, `test`, `[ ]`, `[[ ]]`)
- Write loops (`for`, `while`)

### Theory / Reading
- **Shebang**: `#!/bin/bash` tells the system which interpreter to use
- **Variables**: `NAME="value"`, accessed as `$NAME` or `${NAME}`
- **Command substitution**: `$(command)` or backticks `` `command` ``
- **Exit codes**: `0` = success, non-zero = failure; check with `$?`

### Practical Exercise
Create the following scripts:

**Script 1: `~/ifinmail-scripts/check_service.sh`**
```bash
#!/bin/bash
# Check if a service is running
# Usage: ./check_service.sh <service-name>

SERVICE="$1"

if [ -z "$SERVICE" ]; then
    echo "Usage: $0 <service-name>"
    exit 1
fi

if systemctl is-active --quiet "$SERVICE"; then
    echo "$SERVICE is running"
else
    echo "$SERVICE is NOT running"
fi
```

**Script 2: `~/ifinmail-scripts/backup_configs.sh`**
```bash
#!/bin/bash
# Backup mail configuration files
# Simulates what we will do before changing Postfix/Dovecot configs

BACKUP_DIR="$HOME/ifinmail-backups/$(date +%Y%m%d_%H%M%S)"
CONFIG_PATHS="/etc/postfix /etc/dovecot /etc/rspamd"

mkdir -p "$BACKUP_DIR"

for path in $CONFIG_PATHS; do
    if [ -d "$path" ]; then
        echo "Backing up $path ..."
        cp -r "$path" "$BACKUP_DIR/"
    else
        echo "Skipping $path (not found — will exist after installation)"
    fi
done

echo "Backup complete: $BACKUP_DIR"
ls -la "$BACKUP_DIR"
```

### Checkpoint Questions
1. What does `$?` contain after a command runs?
2. Why do we use `"$SERVICE"` with quotes instead of bare `$SERVICE`?
3. What does `$(date +%Y%m%d)` produce? Why is this useful for backups?
4. How would you modify `check_service.sh` to check multiple services at once?

### Connection to ifinmail App
Shell scripts are used extensively for mail server automation: backing up configs, rotating logs, checking DNS health, running Rspamd training, and more. The proposal's Phase 1 "basic admin CLI" starts as shell scripts.

---

## Day 5 (Friday): Text Processing & The Unix Pipeline

### Learning Objectives
- Use pipes (`|`) to chain commands together
- Filter and search with `grep`
- Transform text with `sed` and `awk`
- Sort, count, and deduplicate with `sort`, `uniq`, `wc`
- Parse log files (preview of mail log analysis)

### Theory / Reading
- **Unix philosophy**: each tool does one thing well; pipes connect them
- **Standard streams**: stdin (0), stdout (1), stderr (2)
- **Redirection**: `>`, `>>`, `2>`, `&>`, `<`

### Practical Exercise
```bash
# Create a sample mail log for practice
mkdir -p ~/ifinmail-scripts
cat > ~/ifinmail-scripts/sample_mail.log << 'EOF'
May 12 10:23:15 mx1 postfix/smtpd[1234]: connect from mail.example.com[192.0.2.1]
May 12 10:23:16 mx1 postfix/smtpd[1234]: NOQUEUE: reject: RCPT from mail.example.com[192.0.2.1]: 554 5.7.1 Service unavailable
May 12 10:23:20 mx1 postfix/smtpd[1235]: connect from trusted.org[203.0.113.5]
May 12 10:23:21 mx1 postfix/smtpd[1235]: 3A4F2C0F: client=trusted.org[203.0.113.5]
May 12 10:23:22 mx1 postfix/qmgr[1000]: 3A4F2C0F: from=<sender@trusted.org>, size=2048
May 12 10:23:23 mx1 postfix/lmtp[1236]: 3A4F2C0F: to=<user@ifinmail.com>, relay=/var/run/dovecot/lmtp, status=sent
May 12 10:23:25 mx1 postfix/qmgr[1000]: 3A4F2C0F: removed
May 12 10:24:01 mx1 dovecot: imap(user@ifinmail.com): Logged in
May 12 10:24:05 mx1 dovecot: imap(user@ifinmail.com): Disconnected
May 12 10:25:30 mx1 postfix/smtpd[1240]: connect from spammer.net[10.0.0.99]
May 12 10:25:31 mx1 postfix/smtpd[1240]: NOQUEUE: reject: spam score 8.5
May 12 10:25:32 mx1 postfix/smtpd[1240]: disconnect from spammer.net[10.0.0.99]
EOF

# --- grep: search and filter ---
echo "=== All rejected connections ==="
grep "reject" ~/ifinmail-scripts/sample_mail.log

echo "=== All connections (connect or disconnect) ==="
grep -E "connect from|disconnect from" ~/ifinmail-scripts/sample_mail.log

echo "=== Lines with queue IDs (alphanumeric queue IDs) ==="
grep -E "[0-9A-F]{7}:" ~/ifinmail-scripts/sample_mail.log

# --- sed: stream editing ---
echo "=== Replace IPs with [REDACTED] ==="
sed 's/\[[0-9.]*\]/[REDACTED]/g' ~/ifinmail-scripts/sample_mail.log

# --- awk: column-based processing ---
echo "=== Extract service and message ==="
awk '{print $4, $5, $6}' ~/ifinmail-scripts/sample_mail.log

# --- sort, uniq, wc: counting and aggregation ---
echo "=== Count lines per service ==="
awk '{print $4}' ~/ifinmail-scripts/sample_mail.log | sort | uniq -c | sort -rn

echo "=== Total log lines ==="
wc -l ~/ifinmail-scripts/sample_mail.log

# --- combined pipeline: most active IPs ---
echo "=== Most active client IPs ==="
grep -oP '\[\K[0-9.]+(?=\])' ~/ifinmail-scripts/sample_mail.log | sort | uniq -c | sort -rn
```

### Checkpoint Questions
1. Why are pipes (`|`) central to Unix philosophy? How does this relate to the ifinmail architecture?
2. How would you find all lines containing "status=sent" and count them?
3. What does `grep -v "^#" /etc/postfix/main.cf` do?
4. How could text processing help automate DNS health checks for ifinmail domains?

### Connection to ifinmail App
Mail servers are log-heavy. Postfix, Dovecot, and Rspamd all write detailed logs. Every sysadmin skill you just practiced (grepping for failures, extracting patterns, counting occurrences) will be used daily when debugging delivery, tracking spam, and monitoring the platform.

---

## Day 6 (Saturday): Review & Integration

### Review Challenge: Mini System Health Script

Write a single script `~/ifinmail-scripts/system_health.sh` that:

1. Prints the current date and hostname
2. Shows disk usage for `/` and `/var` (if separate)
3. Shows memory usage (free and total)
4. Checks if a list of services (postfix, dovecot, rspamd, postgresql, redis) are running
5. Counts the number of failed login attempts in `/var/log/auth.log` (if accessible) or prints "log not accessible"
6. Saves all output to a timestamped file in `~/ifinmail-reports/`

**Stretch goal**: Make the service list configurable via a separate config file.

### Week 1 Self-Assessment

Before moving to Week 2, confirm you can:
- [ ] Navigate the Linux file system without thinking about it
- [ ] Create, read, edit (with nano/vim), move, and delete files
- [ ] Explain `chmod 640` and `chmod 755` to a peer
- [ ] Start, stop, and check the status of a systemd service
- [ ] Write a 20-line shell script with variables, conditionals, and loops
- [ ] Pipe `grep`, `awk`, `sort`, and `uniq` together to analyze a log file
- [ ] SSH into a remote machine

---

## Week 1 Resource Index

| Resource | Location |
|---|---|
| Day 1 exercises | `exercises/day_01_filesystem.md` |
| Day 2 exercises | `exercises/day_02_permissions.md` |
| Day 3 exercises | `exercises/day_03_processes.md` |
| Day 4 scripts | `scripts/check_service.sh`, `scripts/backup_configs.sh` |
| Day 5 sample data | `data/sample_mail.log` |
| Day 6 challenge | `challenges/week_01_health_script.md` |
| Week 1 summary | `summary.md` |

---

*Week 1 of 12 — Linux/Unix Fundamentals for ifinmail Platform Engineering*
