import plotly.express as px
import pandas as pd


class GraphService:

    @staticmethod
    def create_bar_chart(df, x, y, title):

        fig = px.bar(
            df,
            x=x,
            y=y,
            title=title
        )

        return fig.to_html(full_html=False)