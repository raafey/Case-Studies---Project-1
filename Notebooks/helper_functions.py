import pandas as pd
import numpy as np
from sklearn.metrics import r2_score
from sklearn.metrics import mean_squared_error
from sklearn.tree import DecisionTreeRegressor
from sklearn.ensemble import RandomForestRegressor


# function that reads data from csv
def read_data():
    file_path = "../styrian_health_data.xlsx"
    sheet_name = "Sheet 1"
    data_df = pd.read_excel(file_path, sheet_name=sheet_name)

    return data_df


# function to format variable types, remove nans, shuffle data
def format_variables(data, to_filter, drop_values):
    data_df = data.copy()
    data_df.postleitzahl = data_df.postleitzahl.astype('str')
    data_df.geburtsjahr = data_df.geburtsjahr.astype('Int64')
    # data_df.befinden = data_df.befinden.astype('Int64')
    data_df.messwert_bp_sys = pd.to_numeric(data_df.messwert_bp_sys)
    data_df.messwert_bp_dia = pd.to_numeric(data_df.messwert_bp_dia)
    data_df.schaetzwert_bp_sys = pd.to_numeric(data_df.schaetzwert_bp_sys)
    data_df.schaetzwert_by_dia = pd.to_numeric(data_df.schaetzwert_by_dia)

    # adding variable for is_local
    mask = data_df.gemeinde.isna() & data_df.bezirk.isna() & data_df.bundesland.isna()

    # adding variable for age
    age =  data_df["zeit"].dt.year - pd.to_datetime(data_df['geburtsjahr'], format='%Y').dt.year
    data_df["age"] = age.astype("Int64")


    #replacing nans for variables

    data_df.loc[data_df.geschlecht.isna() == True, 'raucher'] = "unknown"
    data_df.loc[data_df.geschlecht.isna() == True, 'blutzucker_bekannt'] = "unknown"
    data_df.loc[data_df.geschlecht.isna() == True, 'cholesterin_bekannt'] = "unknown"
    data_df.loc[data_df.geschlecht.isna() == True, 'in_behandlung'] = "unknown"
    data_df.loc[data_df.geschlecht.isna() == True, 'befinden'] = "unknown"

    data_df.loc[mask, 'gemeinde'] = "not applicable"
    data_df.loc[mask, 'bezirk'] = "not applicable"
    data_df.loc[mask, 'bundesland'] = "not applicable"
    data_df.loc[mask, 'postleitzahl'] = "not applicable"
    data_df.loc[data_df.postleitzahl == "nan", 'postleitzahl'] = "unknown"
    data_df.loc[data_df.geschlecht.isna() == True, 'geschlecht'] = "unknown"

    
    if drop_values:
    # removing useless variables
        data_df.drop(data_df[data_df.age > 100].index, inplace=True)
        data_df.drop(data_df[data_df.age < 15].index, inplace=True)

        # dropping nan values
        data_df = data_df.dropna()

    data_df['befinden'] = data_df['befinden'].astype(object)
    data_df['messwert_bp_sys'] = data_df['messwert_bp_sys'].astype(float)
    data_df['messwert_bp_dia'] = data_df['messwert_bp_dia'].astype(float)
    data_df['geschlecht'] = data_df['geschlecht'].astype(object)

    # dropping values from filter

    if drop_values:
        if len(to_filter) > 0:
            data_df = data_df.drop(to_filter, axis=1)

    # shuffling data with fixed seed
    data_df = data_df.sample(frac=1, random_state=1).reset_index(drop=True)

    # separating var types
    cat_feat_list = []
    num_feat_list = []

    for var in data_df.columns:
        if data_df[var].dtype == object:
            cat_feat_list.append(var)
        else:
            num_feat_list.append(var)

    return data_df, cat_feat_list, num_feat_list


# function that converts cat columns in df to one-hot encoding
def encode_data(df, cat_feat_list, num_feat_list):
    one_hot_data = pd.get_dummies(df[cat_feat_list], drop_first=True, dtype=int)

    for var in num_feat_list:
        one_hot_data[var] = df[var] 
    
    return one_hot_data

# function to separate target from dataframe
def separate_target(data, target):
    df = data.copy()
    Y = df[target]
    del df[target]
    X = df

    return X, Y

# computes adjusted R2
def adjusted_r2(r_2, n, k):
    return 1 - (1-r_2)*(n-1)/(n-k-1)


# function to compute metrics given target and predictions
def compute_metrics(pred, target, num_feats):
    r_2 = r2_score(pred, target)
    mse = mean_squared_error(pred, target)
    adj_r2 = adjusted_r2(r_2, len(pred), num_feats)
    return {
        "r_2": r_2,
        "adjusted_r_2": adj_r2,
        "mse": mse
    }

# method that fits and predicts regression tree based on model type
def fit_and_eval_regression_tree(X_train, Y_train, X_test, params, model_type):
    model = None
    if model_type == "DecisionTreeRegressor":
        model = DecisionTreeRegressor(**params)
    elif model_type == "DecisionTreeRegressorRandomForest":
        model = RandomForestRegressor(**params)

    model.fit(X_train, Y_train)
    train_predictions = model.predict(X_train)
    test_predictions = model.predict(X_test)

    return train_predictions, test_predictions, model

# method that fits, predicts, generates eval metrics for regression tree based on model type
def fit_model(X_train, Y_train, X_test, Y_test, model_type, params):
    num_feats = len(X_train.columns)
    train_predictions = None
    train_predictions = None
    train_results = None
    test_results = None
    model = None

    if model_type in ["DecisionTreeRegressor", "DecisionTreeRegressorRandomForest"]:
        train_predictions, test_predictions, model = fit_and_eval_regression_tree(X_train, Y_train, X_test, params, model_type)

    if train_predictions is not None and test_predictions is not None:
        train_results = compute_metrics(train_predictions, Y_train, num_feats)
        test_results = compute_metrics(test_predictions, Y_test, num_feats)


    return train_results, test_results, model

# method that performs best subset feat selection based on some creiterion like mse, adjusted_r_2 or r_2
def best_subset_selection(features, criterion, X_train, Y_train, X_test, Y_test, model_type, params, verbose):
    if criterion == "mse":
        best_val = np.inf
    elif criterion in ["adjusted_r_2", "r_2"]:
        best_val = -np.inf

    best_train_results = None
    best_model = None
    best_test_results = None
    best_features = None
    n_features = len(features)


    for i in range(1, n_features):
        if verbose > 1:
            print("\nNum features: ", i, "=======================================================")

        for j in range(n_features):
            current_features = features[j:j+i]
            if len(current_features) < i:
                break

            X_train_curr = X_train[current_features]
            X_test_curr = X_test[current_features]
            
            train_results, test_results, model = fit_model(X_train_curr, Y_train, X_test_curr, Y_test, model_type, params)

            if verbose > 1:
                print("\nFeatures: ", current_features)
                print("Train Results: ", train_results)
                print("Test Results: ", test_results)

            condition = False
            if criterion == "mse":
                condition = test_results[criterion] < best_val
            elif criterion in ["adjusted_r_2", "r_2"]:
                condition = test_results[criterion] > best_val   

            if condition:
                best_val = test_results[criterion]
                best_model = model
                best_features = current_features
                best_train_results = train_results
                best_test_results = test_results
    
    if verbose > 0:
        print("\nBest Model: ")
        print("Features: ", best_features)
        print("Train Results: ", best_train_results)
        print("Test Results: ", best_test_results)
    
    return best_model, best_train_results, best_test_results


# method that formats results of different models in a dataframe
def tabularize_model_metrics(train_result_list, test_result_list, model_names):
    train_df = pd.DataFrame(train_result_list)
    test_df = pd.DataFrame(test_result_list)
    train_df = train_df.rename(columns={"adjusted_r_2": "Train Adjusted R2", "r_2": "Train R2", "mse": "Train Mean Sq Error"})
    test_df = test_df.rename(columns={"adjusted_r_2": "Test Adjusted R2", "r_2": "Test R2", "mse": "Test Mean Sq Error"})
    df = pd.concat([train_df, test_df], axis=1)
    df["Model"] = model_names
    return df[["Model", "Train Mean Sq Error", "Test Mean Sq Error", "Train R2", "Test R2", "Train Adjusted R2", "Test Adjusted R2"]]