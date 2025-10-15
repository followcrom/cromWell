import pandas as pd

def parse_fitbit_data(data):
    """Parse the list of measurements into separate DataFrames by measurement type"""
    
    # Group data by measurement type
    measurements_dict = {}
    for record in data:
        measurement = record['measurement']
        if measurement not in measurements_dict:
            measurements_dict[measurement] = []
        measurements_dict[measurement].append(record)
    
    # Convert each measurement type to a DataFrame
    dfs = {}
    
    for measurement, records in measurements_dict.items():
        # Extract data into a flat structure
        parsed_records = []
        for record in records:
            flat_record = {
                'time': pd.to_datetime(record['time']),
            }
            
            # Add ALL tags (not just Device) - THIS WAS THE BUG!
            if 'tags' in record:
                for tag_key, tag_value in record['tags'].items():
                    flat_record[tag_key] = tag_value
            
            # Add all fields
            if 'fields' in record:
                flat_record.update(record['fields'])
            
            parsed_records.append(flat_record)
        
        # Create DataFrame
        df = pd.DataFrame(parsed_records)
        df = df.sort_values('time').reset_index(drop=True)
        
        dfs[measurement] = df
    
    return dfs