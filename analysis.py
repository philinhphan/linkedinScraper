import pandas as pd
import json

def parse_experiences(exp_string):
    """
    Safely parse the JSON-like string of experiences.
    Returns a list of dict, or an empty list if parsing fails.
    """
    if pd.isna(exp_string) or exp_string.strip() == "":
        return []
    try:
        # Clean up or transform the string if needed before parsing
        return json.loads(exp_string)
    except (json.JSONDecodeError, TypeError):
        return []

def parse_education(edu_string):
    """
    Safely parse the JSON-like string of education.
    Returns a list of dict, or an empty list if parsing fails.
    """
    if pd.isna(edu_string) or edu_string.strip() == "":
        return []
    try:
        return json.loads(edu_string)
    except (json.JSONDecodeError, TypeError):
        return []

def analyze_founder_profiles(csv_file_path):
    """
    Reads the CSV file, parses columns, and returns or prints
    summary insights about founder profiles.
    """
    # Read CSV
    df = pd.read_csv(csv_file_path)
    
    # Parse experiences & education columns
    df['parsed_experiences'] = df['experiences'].apply(parse_experiences)
    df['parsed_education']   = df['education'].apply(parse_education)
    
    # Basic transformations/cleaning:
    # Example: count the number of experience entries, the number of education entries, etc.
    df['num_experiences'] = df['parsed_experiences'].apply(len)
    df['num_educations']  = df['parsed_education'].apply(len)

    # ---- Example 1: Summaries across all founders ----
    total_founders = len(df)
    avg_experiences = df['num_experiences'].mean()
    avg_educations  = df['num_educations'].mean()

    # Collect all degrees / schools mentioned to see how often each appears
    all_degrees = []
    all_schools = []
    for edus in df['parsed_education']:
        for edu in edus:
            # 'degree' and 'school' might be repeated or contain newlines
            deg = edu.get('degree', '').replace('\n', ' ').strip()
            sch = edu.get('school', '').replace('\n', ' ').strip()
            if deg:
                all_degrees.append(deg)
            if sch:
                all_schools.append(sch)
                
    degree_counts = pd.Series(all_degrees).value_counts()
    school_counts = pd.Series(all_schools).value_counts()

    # ---- Example 2: Summaries per-founder ----
    # For instance, we can note each founder's last/current role or current headline.
    founder_summaries = []
    for _, row in df.iterrows():
        name = row['name']
        headline = row['headline']
        exp_count = row['num_experiences']
        edu_count = row['num_educations']
        
        # Summarize the degrees for each founder
        degrees_for_person = []
        for edu in row['parsed_education']:
            deg = edu.get('degree', '').replace('\n', ' ').strip()
            if deg:
                degrees_for_person.append(deg)
        
        founder_summaries.append({
            'name': name,
            'headline': headline,
            'num_experiences': exp_count,
            'num_educations': edu_count,
            'degrees': degrees_for_person,
        })
    
    # ---- Print or return a textual summary ----
    print("=====================================")
    print("         FOUNDER PROFILE SUMMARY     ")
    print("=====================================")
    print(f"Total Founders: {total_founders}")
    print(f"Average Number of Experiences: {avg_experiences:.2f}")
    print(f"Average Number of Educations: {avg_educations:.2f}")
    print()
    print("Most Common Degrees:")
    print(degree_counts.head(5))  # top 5
    print()
    print("Most Common Schools:")
    print(school_counts.head(5))
    print()
    print("------- Individual Summaries -------")
    for fs in founder_summaries:
        print(f"- {fs['name']} | {fs['headline']}")
        print(f"  Experiences: {fs['num_experiences']}, Educations: {fs['num_educations']}")
        if fs['degrees']:
            print(f"  Degrees: {', '.join(fs['degrees'])}")
        print("")

    # If desired, return a dictionary or a DataFrame containing the summary
    # instead of printing. For example:
    # return {
    #     "overall": {
    #         "total_founders": total_founders,
    #         "avg_experiences": avg_experiences,
    #         "avg_educations": avg_educations,
    #         "degree_counts": degree_counts.to_dict(),
    #         "school_counts": school_counts.to_dict()
    #     },
    #     "by_founder": founder_summaries
    # }

if __name__ == "__main__":
    csv_path = "founder_profile_data.csv"
    analyze_founder_profiles(csv_path)





# Experience: find groups of companies (founder / co-founder, tech (Meta, Google, ...), 