# import pandas as pd
# import matplotlib.pyplot as plt
# from sqlalchemy.orm import db_session
# from Package.models import Message, Workspace

# def get_messages_df() -> pd.DataFrame:
#     messages = db_session.query(Message).all()
#     return pd.DataFrame([{
#         'sent_at': m.sent_at,
#         'author_id': m.author_id,
#         'workspace_id': m.workspace_id,
#         'content': m.content
#     } for m in messages])
#
# def get_workspaces_df() -> pd.DataFrame:
#     workspaces = db_session.query(Workspace).all()
#     return pd.DataFrame([{
#         'workspace_id': w.workspace_id,
#         'name': w.name,
#         'created_at': w.created_at
#     } for w in workspaces])
#
#
# def daily_message_counts(df: pd.DataFrame) -> pd.Series:
#     df['date'] = pd.to_datetime(df['sent_at']).dt.date
#     return df.groupby('date').size()
#
# def top_authors(df: pd.DataFrame, top_n=5) -> pd.Series:
#     return df['author_id'].value_counts().head(top_n)
#
# def messages_per_workspace(df: pd.DataFrame) -> pd.Series:
#     return df['workspace_id'].value_counts()
#
# def active_days_per_workspace(df: pd.DataFrame) -> pd.Series:
#     df['date'] = pd.to_datetime(df['sent_at']).dt.date
#     return df.groupby('workspace_id')['date'].nunique()
#
# def average_messages_per_day(df: pd.DataFrame) -> float:
#     df['date'] = pd.to_datetime(df['sent_at']).dt.date
#     return df.groupby('date').size().mean()
#
# def plot_messages_per_day(df: pd.DataFrame):
#     daily = daily_message_counts(df)
#     daily.plot(kind='bar', title='Messages Per Day', figsize=(10,4), color='steelblue')
#     plt.xlabel("Date")
#     plt.ylabel("Message Count")
#     plt.tight_layout()
#     plt.show()
#
# def plot_messages_per_workspace(df: pd.DataFrame):
#     workspace_counts = messages_per_workspace(df)
#     workspace_counts.plot(kind='bar', title='Messages Per Workspace', color='teal')
#     plt.xlabel("Workspace ID")
#     plt.ylabel("Messages")
#     plt.tight_layout()
#     plt.show()
#
#
# if __name__ == '__main__':
#     messages_df = get_messages_df()
#     workspaces_df = get_workspaces_df()
#
#     print("Messages Preview:")
#     print(messages_df.head())
#
#     print("Workspaces Preview:")
#     print(workspaces_df.head())
#
#     print("Daily Message Counts:")
#     print(daily_message_counts(messages_df))
#
#     print("Top Authors:")
#     print(top_authors(messages_df))
#
#     print("Messages Per Workspace:")
#     print(messages_per_workspace(messages_df))
#
#     print("Active Days Per Workspace:")
#     print(active_days_per_workspace(messages_df))
#
#     print("Average Messages Per Day:")
#     print(round(average_messages_per_day(messages_df), 2))
#
#     plot_messages_per_day(messages_df)
#     plot_messages_per_workspace(messages_df)
