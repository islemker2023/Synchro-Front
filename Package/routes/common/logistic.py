# import numpy as np
# import pandas as pd
# from datetime import datetime
# from sklearn.linear_model import LogisticRegression
#
# from Package import db_session
# from Package.models import Message, Workspace
#
# def load_workspace_message_data():
#
#     messages = db_session.query(Message).all()
#     message_dict = []
#     for m in messages:
#         message_dict.append({
#             'workspace_id': m.workspace_id,
#             'sent_at': m.sent_at
#         })
#     message_data = pd.DataFrame(message_dict)
#
#     workspaces = db_session.query(Workspace).all()
#     workspace_dict = []
#     for w in workspaces:
#         workspace_dict.append({
#             'workspace_id': w.workspace_id,
#             'created_at': w.created_at
#         })
#     workspace_data = pd.DataFrame(workspace_dict)
#     return message_data, workspace_data
#
# def build_features_labels(message_df, workspace_df):
#     message_counts = message_df.groupby('workspace_id').size().reset_index(name='message_count')
#
#     last_activity = message_df.groupby('workspace_id')['sent_at'].max().reset_index(name='last_message')
#
#     df = workspace_df.merge(message_counts, on='workspace_id', how='left')
#     df['message_count'] = df['message_count'].fillna(0)
#     df = df.merge(last_activity, on='workspace_id', how='left')
#     df['last_message'] = df['last_message'].fillna(df['created_at'])
#
#     df['created_at'] = pd.to_datetime(df['created_at'])
#     df['last_message'] = pd.to_datetime(df['last_message'])
#     df['days_active'] = df['last_message'] - df['created_at']
#     df['days_active'] = df['days_active'].dt.days
#     df['days_active'] = df['days_active'].clip(lower=0)
#
#     df['is_active'] = 0
#     df.loc[(df['message_count'] > 20) & (df['days_active'] > 7), 'is_active'] = 1
#
#     features = df[['message_count', 'days_active']]
#     labels = df['is_active']
#
#     return features, labels, df
#
# def train_model(X, y):
#     model = LogisticRegression()
#     model.fit(X, y)
#     return model
#
# def predict_workspace_activity(model, X):
#     predictions = model.predict(X)
#     return predictions
#
# if __name__ == '__main__':
#     messages_df, workspaces_df = load_workspace_message_data()
#     X, y, full_df = build_features_labels(messages_df, workspaces_df)
#     model = train_model(X, y)
#     predictions = predict_workspace_activity(model, X)
#     full_df['predicted_active'] = predictions
#     print("📊 Predicted Workspace Activity:")
#     print(full_df[['workspace_id', 'message_count', 'days_active', 'is_active', 'predicted_active']].head(10))
