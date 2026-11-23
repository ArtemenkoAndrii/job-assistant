Open the LinkedIn vacancy {url} and extract it. The full text is in the job details pane.
data: {"title": str, "company": str, "location": str, "work_type": "remote|hybrid|on-site|unknown", "employment_type": str|null,
 "seniority": str|null, "salary": str|null, "required_skills": [str], "nice_to_have_skills": [str],
 "apply_method": "easy_apply|external|email|unknown", "apply_url": str|null, "company_page": str|null, "summary": str (max 60 words)}
