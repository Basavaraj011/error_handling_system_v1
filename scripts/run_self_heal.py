from src.plugins.self_heal.code_modifier import CodeModifier
from src.plugins.self_heal.pr_creator import open_pr
from connections.vcs import get_provider
from config.settings import BITBUCKET,DATABASE_URL
from database.database_operations import DatabaseManager, fetch_errors_from_db
from src.plugins.self_heal.search_similar_solutions import search_similar_solutions



def provider_opts(repo_slug: str):
    return dict(
        workspace=BITBUCKET["workspace"],
        repo_slug=repo_slug,
        api_username=BITBUCKET["api_username"],
        git_username=BITBUCKET["git_username"],
        app_password=BITBUCKET["auth_token"],
        reviewers=[],
    )


def main():

    db_manager = DatabaseManager(DATABASE_URL)
    print("Fetching errors from database...")
    errors = fetch_errors_from_db(limit=None, severity_filter=None, db_manager=db_manager)
    if len(errors)==0:
        print("*****No Errors Found To Process****")
        return False
    print(f"Fetched {len(errors)} errors from database.")
    past_solutions = search_similar_solutions(errors, db_manager)
    print("Similar solution found:", past_solutions)
    if past_solutions != None:
        prev_solution = past_solutions[0].get('proposed_solution')
        prev_error = past_solutions[0].get('cleaned_stack_trace')
    else:
        prev_solution, prev_error = None, None
    

    # print("\n===== RUNNING SELF HEAL 2 =====")
    repo_slug = 'error_pipeline_demo'

    # 2️⃣ Clone Repo
    provider = get_provider("bitbucket", **provider_opts(repo_slug))
    repo_dir = provider.clone_repo()
    print("[CLONE] →", repo_dir)

    # 3️⃣ Apply Fix (AI finds the file + patch)
    cm = CodeModifier(repo_path=repo_dir)
    changed_files = []

    res = cm.apply_fix(
        repo_name=repo_slug,
        error_stack_trace=errors[0].get('stack_trace'),
        prev_error=prev_error,
        prev_solution=prev_solution
    )

    print("Changed file:", res["file"])
    print("Patch:\n", res["patch"])
    print("Solution:", res["solution"])

    changed_files.append(res["file"])

    changed_files = sorted(set(changed_files))
    print("Changed files:", changed_files)

    if not changed_files:
        print("[SKIP] No modifications detected.")
        return

    # 5️⃣ Create PR using open_pr()
    pr = open_pr(
        provider_kind="bitbucket",
        provider_opts=provider_opts(repo_slug),
        engine_root=repo_dir,
        solution=res["solution"],
        changed_files_rel=changed_files,
        base_branch="main",
        ticket_key="AUTO",
    )

    print("PR CREATED:", pr.get("links", {}).get("html", {}).get("href", ""))


if __name__ == "__main__":
    main()