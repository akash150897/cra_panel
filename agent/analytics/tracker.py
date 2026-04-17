"""Analytics tracker for monitoring developer activity."""
import json
import os
import re
import subprocess
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path

from agent.database import DatabaseManager


class AnalyticsTracker:
    """Tracks developer activity from git history and code reviews."""

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()

    def get_git_email(self, project_path: str) -> str:
        """Get git user email from project."""
        try:
            result = subprocess.run(
                ["git", "config", "user.email"],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def analyze_commit(self, project_path: str, commit_hash: str = "HEAD") -> Dict[str, Any]:
        """Analyze a single commit for metrics."""
        try:
            # Get commit stats
            result = subprocess.run(
                ["git", "show", "--stat", "--format=%H|%an|%ae|%ad", commit_hash],
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=10
            )

            lines = result.stdout.strip().split('\n')
            if not lines:
                return {}

            # Parse header
            header = lines[0].split('|')
            if len(header) < 4:
                return {}

            commit_data = {
                'hash': header[0],
                'author_name': header[1],
                'author_email': header[2],
                'date': header[3],
                'files_changed': 0,
                'insertions': 0,
                'deletions': 0
            }

            # Parse stats from last line
            if lines:
                last_line = lines[-1]
                # Match patterns like "5 files changed, 100 insertions(+), 20 deletions(-)"
                files_match = re.search(r'(\d+) file', last_line)
                insertions_match = re.search(r'(\d+) insertion', last_line)
                deletions_match = re.search(r'(\d+) deletion', last_line)

                if files_match:
                    commit_data['files_changed'] = int(files_match.group(1))
                if insertions_match:
                    commit_data['insertions'] = int(insertions_match.group(1))
                if deletions_match:
                    commit_data['deletions'] = int(deletions_match.group(1))

            return commit_data
        except Exception as e:
            print(f"[Analytics] Error analyzing commit: {e}")
            return {}

    def get_commits_for_date(self, project_path: str, target_date: date,
                             author_email: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get all commits for a specific date."""
        try:
            date_str = target_date.strftime('%Y-%m-%d')
            since = f"{date_str} 00:00:00"
            until = f"{date_str} 23:59:59"

            cmd = [
                "git", "log",
                f"--since={since}",
                f"--until={until}",
                "--format=%H|%an|%ae|%ad",
                "--no-merges"
            ]

            if author_email:
                cmd.extend(["--author", author_email])

            result = subprocess.run(
                cmd,
                cwd=project_path,
                capture_output=True,
                text=True,
                timeout=30
            )

            commits = []
            for line in result.stdout.strip().split('\n'):
                if not line:
                    continue
                parts = line.split('|')
                if len(parts) >= 4:
                    commits.append({
                        'hash': parts[0],
                        'author_name': parts[1],
                        'author_email': parts[2],
                        'date': parts[3]
                    })

            # Get stats for each commit
            for commit in commits:
                stats = self.analyze_commit(project_path, commit['hash'])
                commit.update(stats)

            return commits
        except Exception as e:
            print(f"[Analytics] Error getting commits: {e}")
            return []

    def analyze_code_quality(self, project_path: str, files: List[str]) -> Dict[str, int]:
        """Run code review and count issues."""
        from agent.detector.language_detector import LanguageDetector
        from agent.utils.config_manager import ConfigManager
        from agent.rules.rule_loader import RuleLoader
        from agent.rules.rule_engine import RuleEngine
        from agent.analyzer.python_analyzer import PythonAnalyzer
        from agent.analyzer.javascript_analyzer import JavaScriptAnalyzer

        try:
            config = ConfigManager()
            lang = LanguageDetector(project_path).detect_primary_language()

            loader = RuleLoader()
            rules = loader.load_rules(language=lang, framework=None)
            engine = RuleEngine(python_analyzer=PythonAnalyzer(), js_analyzer=JavaScriptAnalyzer())
            result = engine.review_files(files, rules, config.max_file_size_bytes, config.exclude_paths)

            return {
                'total_issues': len(result.violations),
                'errors': len(result.errors),
                'warnings': len(result.warnings),
                'infos': len(result.infos)
            }
        except Exception as e:
            print(f"[Analytics] Error analyzing code quality: {e}")
            return {'total_issues': 0, 'errors': 0, 'warnings': 0, 'infos': 0}

    def calculate_effort_score(self, commits: List[Dict[str, Any]],
                                issues_found: int, issues_fixed: int = 0) -> float:
        """Calculate effort score based on activity and quality."""
        if not commits:
            return 0.0

        total_lines = sum(c.get('insertions', 0) + c.get('deletions', 0) for c in commits)
        total_files = sum(c.get('files_changed', 0) for c in commits)
        commit_count = len(commits)

        # Base score from activity
        score = min(commit_count * 10, 50)  # Max 50 from commits
        score += min(total_files * 2, 20)  # Max 20 from files
        score += min(total_lines / 10, 20)  # Max 20 from lines

        # Quality penalty/bonus
        if issues_found == 0:
            score += 10  # Clean code bonus
        else:
            score -= min(issues_found * 2, 20)  # Max 20 penalty for issues

        # Bonus for fixing bugs
        score += min(issues_fixed * 5, 15)

        return max(0.0, min(100.0, score))

    def calculate_quality_score(self, violations_count: int, total_lines: int) -> float:
        """Calculate code quality score (0-100)."""
        if total_lines == 0:
            return 100.0

        # Issues per 100 lines
        density = (violations_count / total_lines) * 100

        # Score decreases as density increases
        if density == 0:
            return 100.0
        elif density < 1:
            return 95.0
        elif density < 3:
            return 85.0
        elif density < 5:
            return 70.0
        elif density < 10:
            return 50.0
        else:
            return max(0.0, 100 - density * 5)

    def list_project_branches(self, project_path: str) -> List[str]:
        """List all local/remote branches for a project path (local clone)."""
        if not project_path or not os.path.exists(project_path):
            return []
        branches = set()
        try:
            # Remote branches
            result = subprocess.run(
                ["git", "-C", project_path, "branch", "-r"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    line = line.strip()
                    if not line or "->" in line:
                        continue
                    b = line.replace("origin/", "", 1)
                    if b:
                        branches.add(b)
            # Local branches
            result = subprocess.run(
                ["git", "-C", project_path, "branch"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    b = line.replace("*", "").strip()
                    if b:
                        branches.add(b)
        except Exception as e:
            print(f"[Analytics] list_project_branches error: {e}")
        return sorted(branches)

    def get_commits_for_user_on_branch(self, project_path: str, branch: str,
                                        user_email: str, since_days: int = 365) -> List[Dict[str, Any]]:
        """Get all commits by a user on a specific branch, grouped per-commit with stats."""
        if not project_path or not os.path.exists(project_path):
            return []
        try:
            since = f"{since_days}.days.ago"
            ref = f"origin/{branch}" if branch else "HEAD"
            # Fall back to local branch name if remote ref doesn't exist
            check = subprocess.run(
                ["git", "-C", project_path, "rev-parse", "--verify", ref],
                capture_output=True, text=True, timeout=10
            )
            if check.returncode != 0:
                ref = branch
                check = subprocess.run(
                    ["git", "-C", project_path, "rev-parse", "--verify", ref],
                    capture_output=True, text=True, timeout=10
                )
                if check.returncode != 0:
                    return []

            cmd = [
                "git", "-C", project_path, "log", ref,
                f"--author={user_email}",
                f"--since={since}",
                "--no-merges",
                "--pretty=format:%H|%an|%ae|%ad",
                "--date=short",
                "--shortstat",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return []

            commits = []
            lines = result.stdout.splitlines()
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if not line:
                    i += 1
                    continue
                if "|" in line and line.count("|") >= 3:
                    parts = line.split("|")
                    entry = {
                        "hash": parts[0],
                        "author_name": parts[1],
                        "author_email": parts[2],
                        "date": parts[3],
                        "files_changed": 0,
                        "insertions": 0,
                        "deletions": 0,
                    }
                    # Look ahead for shortstat line
                    if i + 1 < len(lines):
                        stat_line = lines[i + 1].strip()
                        if "changed" in stat_line or "insertion" in stat_line or "deletion" in stat_line:
                            files_m = re.search(r"(\d+) file", stat_line)
                            ins_m = re.search(r"(\d+) insertion", stat_line)
                            del_m = re.search(r"(\d+) deletion", stat_line)
                            if files_m:
                                entry["files_changed"] = int(files_m.group(1))
                            if ins_m:
                                entry["insertions"] = int(ins_m.group(1))
                            if del_m:
                                entry["deletions"] = int(del_m.group(1))
                            i += 1  # consume stat line
                    commits.append(entry)
                i += 1
            return commits
        except Exception as e:
            print(f"[Analytics] get_commits_for_user_on_branch error on {branch}: {e}")
            return []

    # ──────────────────────────────────────────────────────────────
    # Git-derived developer activity (authoritative source of truth)
    # ──────────────────────────────────────────────────────────────

    def get_files_touched_by_user(self, project_path: str, user_email: str,
                                   since_days: int = 7,
                                   branch: Optional[str] = None) -> set:
        """Return a SET of normalized file paths modified by the user.

        Uses `git log --name-only --author=<email>`. When branch is given,
        limits log to that branch; otherwise scans across the repo.
        """
        if not project_path or not os.path.exists(project_path):
            return set()
        try:
            since = f"{since_days}.days.ago"
            cmd = ["git", "-C", project_path, "log",
                   f"--author={user_email}", f"--since={since}",
                   "--no-merges", "--name-only", "--pretty=format:"]
            if branch:
                # Prefer remote ref if present
                ref_check = subprocess.run(
                    ["git", "-C", project_path, "rev-parse", "--verify", f"origin/{branch}"],
                    capture_output=True, text=True, timeout=5
                )
                ref = f"origin/{branch}" if ref_check.returncode == 0 else branch
                # Insert ref before filters: git log <ref> --author=...
                cmd = ["git", "-C", project_path, "log", ref,
                       f"--author={user_email}", f"--since={since}",
                       "--no-merges", "--name-only", "--pretty=format:"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if result.returncode != 0:
                return set()
            files = set()
            for line in result.stdout.splitlines():
                p = line.strip().replace("\\", "/").lstrip("./")
                if p:
                    files.add(p)
            return files
        except Exception as e:
            print(f"[Analytics] get_files_touched_by_user error: {e}")
            return set()

    def get_developer_activity(self, project_path: str, user_email: str,
                               since_days: int = 7) -> Dict[str, Any]:
        """Aggregate a developer's git activity across ALL branches.

        Returns:
            {
              "total_commits": int,            # unique SHAs authored in window
              "lines_added": int,
              "lines_removed": int,
              "files_touched": int,
              "current_branch": str|None,      # branch of most-recent commit
              "latest_commit_date": str|None,  # ISO
              "branches": [                    # per-branch breakdown
                 {"name": str, "commits": int, "last_date": str,
                  "first_date": str, "unique_commits": int}
              ]
            }

        Commits that appear on multiple branches are NOT double-counted in
        `total_commits`; each branch row shows how many of its commits were
        authored by the user (which may overlap with other branches).
        """
        empty = {
            "total_commits": 0, "lines_added": 0, "lines_removed": 0,
            "files_touched": 0, "current_branch": None,
            "latest_commit_date": None, "branches": [],
        }
        if not project_path or not os.path.exists(project_path):
            return empty

        try:
            subprocess.run(
                ["git", "-C", project_path, "fetch", "--all", "--prune"],
                capture_output=True, text=True, timeout=30
            )
        except Exception:
            pass

        all_branches = self.list_project_branches(project_path)
        if not all_branches:
            return empty

        # Track unique SHAs across branches → dedup total commits/lines
        seen_shas: Dict[str, Dict[str, Any]] = {}
        per_branch: List[Dict[str, Any]] = []

        for br in all_branches:
            commits = self.get_commits_for_user_on_branch(
                project_path, br, user_email, since_days=since_days
            )
            if not commits:
                continue
            dates = sorted([c.get("date", "") for c in commits if c.get("date")])
            last_date = dates[-1] if dates else None
            first_date = dates[0] if dates else None
            per_branch.append({
                "name": br,
                "commits": len(commits),
                "unique_commits": len({c["hash"] for c in commits if c.get("hash")}),
                "last_date": last_date,
                "first_date": first_date,
            })
            for c in commits:
                sha = c.get("hash")
                if not sha or sha in seen_shas:
                    continue
                seen_shas[sha] = c

        total_commits = len(seen_shas)
        lines_added = sum(c.get("insertions", 0) for c in seen_shas.values())
        lines_removed = sum(c.get("deletions", 0) for c in seen_shas.values())
        files_touched = len(self.get_files_touched_by_user(
            project_path, user_email, since_days=since_days
        ))

        # Current branch = branch containing the user's latest commit
        current_branch = None
        latest_date = None
        for b in per_branch:
            if b["last_date"] and (latest_date is None or b["last_date"] > latest_date):
                latest_date = b["last_date"]
                current_branch = b["name"]

        # Sort branches most-recent first
        per_branch.sort(key=lambda b: (b.get("last_date") or ""), reverse=True)

        return {
            "total_commits": total_commits,
            "lines_added": lines_added,
            "lines_removed": lines_removed,
            "files_touched": files_touched,
            "current_branch": current_branch,
            "latest_commit_date": latest_date,
            "branches": per_branch,
        }

    def backfill_user_history(self, project_id: int, project_path: str,
                              user_email: str, since_days: int = 365) -> Dict[str, Any]:
        """Walk git history for a user across ALL branches and populate
        developer_analytics so analytics shows up immediately after a
        developer is assigned to an existing project.

        Returns a summary dict: {branches_found, commits_imported, days_logged}.
        """
        summary = {"branches_found": 0, "commits_imported": 0, "days_logged": 0,
                   "branches": [], "errors": []}
        if not project_path or not os.path.exists(project_path):
            summary["errors"].append(
                f"Project path not accessible locally for backfill: {project_path}. "
                "Clone the repo locally and re-run."
            )
            return summary

        # Ensure origin refs are up to date if this is a git repo with a remote
        try:
            subprocess.run(
                ["git", "-C", project_path, "fetch", "--all", "--prune"],
                capture_output=True, text=True, timeout=60
            )
        except Exception:
            pass  # fetch failure shouldn't block backfill

        branches = self.list_project_branches(project_path)
        summary["branches_found"] = len(branches)
        summary["branches"] = branches

        for branch in branches:
            commits = self.get_commits_for_user_on_branch(
                project_path, branch, user_email, since_days=since_days
            )
            if not commits:
                continue

            # Group commits by date → aggregate per (branch, date)
            per_day: Dict[str, Dict[str, int]] = {}
            for c in commits:
                d_str = c.get("date") or ""
                if not d_str:
                    continue
                bucket = per_day.setdefault(d_str, {
                    "commits": 0, "insertions": 0, "deletions": 0, "files": 0,
                })
                bucket["commits"] += 1
                bucket["insertions"] += c.get("insertions", 0)
                bucket["deletions"] += c.get("deletions", 0)
                bucket["files"] += c.get("files_changed", 0)

            for d_str, stats in per_day.items():
                try:
                    target_date = datetime.strptime(d_str, "%Y-%m-%d").date()
                except Exception:
                    continue
                total_lines = stats["insertions"] + stats["deletions"]
                # No quality scan for historical commits; use neutral placeholders.
                quality = 100.0
                effort = min(100.0, stats["commits"] * 10 + min(stats["files"] * 2, 20)
                             + min(total_lines / 10, 20))
                ok = self.db.log_analytics(
                    user_email=user_email,
                    project_id=project_id,
                    date=target_date,
                    branch=branch,
                    commits_count=stats["commits"],
                    lines_added=stats["insertions"],
                    lines_removed=stats["deletions"],
                    issues_found=0,
                    bugs_fixed=0,
                    files_changed=stats["files"],
                    code_quality_score=quality,
                    effort_score=effort,
                )
                if ok:
                    summary["days_logged"] += 1
            summary["commits_imported"] += len(commits)

        return summary

    def track_daily_activity(self, project_id: int, project_path: str,
                            user_email: str, target_date: Optional[date] = None) -> bool:
        """Track and store daily activity for a developer."""
        if not target_date:
            target_date = date.today()

        try:
            # Get commits for the date
            commits = self.get_commits_for_date(project_path, target_date, user_email)

            if not commits:
                # Still log a zero-activity day
                self.db.log_analytics(
                    user_email=user_email,
                    project_id=project_id,
                    date=target_date,
                    commits_count=0,
                    lines_added=0,
                    lines_removed=0,
                    issues_found=0,
                    bugs_fixed=0,
                    files_changed=0,
                    code_quality_score=100.0,
                    effort_score=0.0
                )
                return True

            # Aggregate commit stats
            total_commits = len(commits)
            total_insertions = sum(c.get('insertions', 0) for c in commits)
            total_deletions = sum(c.get('deletions', 0) for c in commits)
            total_files = sum(c.get('files_changed', 0) for c in commits)

            # Analyze code quality (on current state)
            from agent.git.git_utils import scan_directory
            from agent.detector.language_detector import LanguageDetector

            lang = LanguageDetector(project_path).detect_primary_language()
            files = scan_directory(project_path, lang, [])
            quality = self.analyze_code_quality(project_path, files)

            # Calculate scores
            total_lines = total_insertions + total_deletions
            quality_score = self.calculate_quality_score(quality['total_issues'], max(total_lines, 1))
            effort_score = self.calculate_effort_score(commits, quality['total_issues'])

            # Log to database
            self.db.log_analytics(
                user_email=user_email,
                project_id=project_id,
                date=target_date,
                commits_count=total_commits,
                lines_added=total_insertions,
                lines_removed=total_deletions,
                issues_found=quality['total_issues'],
                bugs_fixed=0,  # Would need issue tracking integration
                files_changed=total_files,
                code_quality_score=quality_score,
                effort_score=effort_score
            )

            return True
        except Exception as e:
            print(f"[Analytics] Error tracking activity: {e}")
            return False

    def get_analytics_summary(self, project_id: Optional[int] = None,
                             user_email: Optional[str] = None,
                             days: int = 7,
                             branch: Optional[str] = None) -> Dict[str, Any]:
        """Team / project analytics derived from git + project_scans.

        Design (agreed with user):
          * Commits / current_branch / all_branches: from git log per developer
            (unique SHAs, deduped across branches).
          * Issue totals per project: MAX across latest scans of each branch
            (never sum — same file exists on multiple branches).
          * Per-developer issues: attributed via file-touch intersection with
            the LATEST scan of their `current_branch`. Computed per branch too.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=days)

        try:
            # ── 1. Determine projects in scope ────────────────────────
            projects_scope: List[Dict[str, Any]] = []
            all_projects = self.db.get_all_projects() if hasattr(self.db, 'get_all_projects') else []
            if project_id is not None:
                projects_scope = [p for p in all_projects if p.get('id') == project_id]
            else:
                projects_scope = list(all_projects)

            # ── 2. Determine developers in scope ──────────────────────
            #    Union of: users assigned to scoped projects, plus `user_email` filter.
            dev_emails: Dict[str, Dict[str, Any]] = {}
            for p in projects_scope:
                assigns = self.db.get_project_assignments(p['id']) if hasattr(self.db, 'get_project_assignments') else []
                for a in assigns:
                    em = a.get('user_email')
                    if not em:
                        continue
                    if user_email and em != user_email:
                        continue
                    if em not in dev_emails:
                        dev_emails[em] = {
                            'name': a.get('name') or em,
                            'email': em,
                            'projects': {},  # project_id -> name
                        }
                    dev_emails[em]['projects'][p['id']] = p.get('name', f"project_{p['id']}")
            if user_email and user_email not in dev_emails:
                # Developer not formally assigned but explicitly requested
                u = self.db.get_user_by_email(user_email) if hasattr(self.db, 'get_user_by_email') else None
                if u:
                    dev_emails[user_email] = {
                        'name': u.get('name') or user_email,
                        'email': user_email,
                        'projects': {p['id']: p.get('name', '') for p in projects_scope},
                    }

            # ── 3. Pre-load latest scans per (project, branch) ────────
            scans_by_project: Dict[int, List[Dict[str, Any]]] = {}
            for p in projects_scope:
                scans = self.db.get_project_scans(project_id=p['id']) if hasattr(self.db, 'get_project_scans') else []
                scans_by_project[p['id']] = scans

            # ── 4. Project-level issue totals (MAX across branches) ──
            #     Also collect per-branch breakdown for UI transparency.
            project_issue_summary: List[Dict[str, Any]] = []
            total_issues_max = 0
            total_errors_max = 0
            total_warnings_max = 0
            total_infos_max = 0
            for p in projects_scope:
                scans = scans_by_project.get(p['id'], [])
                if not scans:
                    continue
                # Optional branch filter
                scans_filt = [s for s in scans if (branch is None or s['branch'] == branch)]
                if not scans_filt:
                    continue
                max_scan = max(scans_filt, key=lambda s: s.get('total_issues', 0))
                total_issues_max += int(max_scan.get('total_issues', 0) or 0)
                total_errors_max += int(max_scan.get('errors', 0) or 0)
                total_warnings_max += int(max_scan.get('warnings', 0) or 0)
                total_infos_max += int(max_scan.get('infos', 0) or 0)
                project_issue_summary.append({
                    'project_id': p['id'],
                    'project_name': p.get('name'),
                    'max_branch': max_scan['branch'],
                    'max_issues': int(max_scan.get('total_issues', 0) or 0),
                    'branches': [
                        {
                            'branch': s['branch'],
                            'issues': int(s.get('total_issues', 0) or 0),
                            'errors': int(s.get('errors', 0) or 0),
                            'warnings': int(s.get('warnings', 0) or 0),
                            'infos': int(s.get('infos', 0) or 0),
                            'scanned_at': (s.get('scanned_at').isoformat()
                                           if hasattr(s.get('scanned_at'), 'isoformat')
                                           else str(s.get('scanned_at'))),
                        }
                        for s in scans_filt
                    ],
                })

            # ── 5. Per-developer git activity + attributed issues ────
            developers: List[Dict[str, Any]] = []
            total_unique_commits = 0
            quality_scores: List[float] = []

            for email, meta in dev_emails.items():
                dev_total_commits = 0
                dev_lines_added = 0
                dev_lines_removed = 0
                dev_files_touched = 0
                dev_branch_stats: List[Dict[str, Any]] = []
                dev_current_branch: Optional[str] = None
                dev_latest_date: Optional[str] = None
                # For "Issues" we use MAX across branches of attributed issues.
                dev_attributed_issues_max = 0
                dev_quality_weighted: List[float] = []

                for p in projects_scope:
                    if p['id'] not in meta['projects']:
                        continue
                    p_path = p.get('path')
                    if not p_path or not os.path.exists(p_path):
                        continue
                    act = self.get_developer_activity(p_path, email, since_days=days)
                    dev_total_commits += act.get('total_commits', 0)
                    dev_lines_added += act.get('lines_added', 0)
                    dev_lines_removed += act.get('lines_removed', 0)
                    dev_files_touched += act.get('files_touched', 0)

                    # Track current branch across projects: pick the latest
                    if act.get('latest_commit_date'):
                        if dev_latest_date is None or act['latest_commit_date'] > dev_latest_date:
                            dev_latest_date = act['latest_commit_date']
                            dev_current_branch = act.get('current_branch')

                    # For each branch the dev has commits on, intersect touched
                    # files with the latest scan's files_with_issues on THAT branch.
                    scans_map = {s['branch']: s for s in scans_by_project.get(p['id'], [])}
                    for br_info in act.get('branches', []):
                        br_name = br_info['name']
                        touched = self.get_files_touched_by_user(
                            p_path, email, since_days=days, branch=br_name
                        )
                        scan = scans_map.get(br_name)
                        attributed = 0
                        attr_errors = attr_warns = attr_infos = 0
                        if scan and touched:
                            files_with_issues = scan.get('files_with_issues') or {}
                            if isinstance(files_with_issues, str):
                                try:
                                    files_with_issues = json.loads(files_with_issues)
                                except Exception:
                                    files_with_issues = {}
                            for fp in touched:
                                bucket = files_with_issues.get(fp)
                                if bucket:
                                    attributed += int(bucket.get('total', 0))
                                    attr_errors += int(bucket.get('errors', 0))
                                    attr_warns += int(bucket.get('warnings', 0))
                                    attr_infos += int(bucket.get('infos', 0))
                        dev_branch_stats.append({
                            'name': br_name,
                            'project_id': p['id'],
                            'project_name': p.get('name'),
                            'commits': br_info.get('commits', 0),
                            'last_date': br_info.get('last_date'),
                            'first_date': br_info.get('first_date'),
                            'issues': attributed,
                            'errors': attr_errors,
                            'warnings': attr_warns,
                            'infos': attr_infos,
                            'quality': (float(scan['quality_score']) if scan and scan.get('quality_score') is not None else None),
                            'scanned_at': (scan.get('scanned_at').isoformat() if scan and hasattr(scan.get('scanned_at'), 'isoformat')
                                            else (str(scan.get('scanned_at')) if scan else None)),
                        })
                        if attributed > dev_attributed_issues_max:
                            dev_attributed_issues_max = attributed
                        if scan and scan.get('quality_score') is not None:
                            dev_quality_weighted.append(float(scan['quality_score']))

                total_unique_commits += dev_total_commits

                # Sort branches by recency
                dev_branch_stats.sort(key=lambda b: (b.get('last_date') or ''), reverse=True)
                branches_list = [b['name'] for b in dev_branch_stats]
                dev_quality = round(sum(dev_quality_weighted) / len(dev_quality_weighted), 1) if dev_quality_weighted else 0
                if dev_quality:
                    quality_scores.append(dev_quality)

                developers.append({
                    'name': meta['name'],
                    'email': email,
                    'commits': dev_total_commits,
                    'lines_added': dev_lines_added,
                    'lines_removed': dev_lines_removed,
                    'files_touched': dev_files_touched,
                    'issues': dev_attributed_issues_max,   # MAX across branches
                    'quality_score': dev_quality,
                    'effort_score': 0,  # (legacy — kept for compat)
                    'current_branch': dev_current_branch,
                    'latest_commit_date': dev_latest_date,
                    'branches': branches_list,
                    'branch_count': len(branches_list),
                    'branch_stats': dev_branch_stats,
                    'projects': list(meta['projects'].values()),
                    'project_count': len(meta['projects']),
                })

            avg_quality = round(sum(quality_scores) / len(quality_scores), 1) if quality_scores else 0

            return {
                'total_commits': total_unique_commits,
                'total_issues': total_issues_max,            # MAX across branches (project totals)
                'total_errors': total_errors_max,
                'total_warnings': total_warnings_max,
                'total_infos': total_infos_max,
                'avg_quality': avg_quality,
                'avg_effort': 0,
                'developers': developers,
                'project_summary': project_issue_summary,    # per-project, per-branch breakdown
                'period': f"{start_date} to {end_date}",
                'aggregation': 'max_across_branches',
            }
        except Exception as e:
            import traceback
            print(f"[Analytics] Error getting summary: {e}")
            traceback.print_exc()
            return {
                'total_commits': 0,
                'total_issues': 0,
                'avg_quality': 0,
                'avg_effort': 0,
                'developers': [],
                'project_summary': [],
                'error': str(e)
            }


# Global instance
_tracker: Optional[AnalyticsTracker] = None


def get_tracker() -> AnalyticsTracker:
    """Get or create the global analytics tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = AnalyticsTracker()
    return _tracker
