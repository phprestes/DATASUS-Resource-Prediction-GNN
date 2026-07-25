import pandas as pd
import numpy as np
from relbench.base import EntityTask, TaskType
from relbench.base import Database
from relbench.metrics import rmse

class PredictBedsTask(EntityTask):
    r"""
    A Task predicts the number of beds (qt_exist in rlEstabComplementar)
    added/existing in the next period for each target hospital (tbEstabelecimento).
    """
    
    task_type = TaskType.REGRESSION
    entity_table = "tbEstabelecimento"
    entity_col = "co_unidade"
    time_col = "timestamp"
    target_col = "qt_exist"
    metrics = [rmse]
    timedelta = pd.Timedelta(days=730)
    
    def make_table(self, db: Database, timestamps: "list[pd.Timestamp]"):
        if "rlEstabComplementar" not in db.table_dict:
            raise ValueError("rlEstabComplementar table not found in DB")
            
        df_beds_pa = db.table_dict["rlEstabComplementar"].df
        time_field = "to_chardt_atualizacaoddmmyyyy"
        
        if hasattr(df_beds_pa, "select"):
            df_beds = df_beds_pa.select(["co_unidade", "qt_exist", time_field]).to_pandas()
            ent_pa = db.table_dict[self.entity_table].df[self.entity_col]
            valid_entities = pd.Series(ent_pa).unique()
        else:
            df_beds = df_beds_pa
            valid_entities = db.table_dict[self.entity_table].df[self.entity_col].unique()
        
        results = []
        for t in timestamps:
            mask = (df_beds[time_field] >= t) & (df_beds[time_field] < t + self.timedelta)
            future_df = df_beds[mask]
            
            # Aggregate total beds per entity
            target_df = future_df.groupby("co_unidade")["qt_exist"].sum().reset_index()
            target_df = target_df[target_df["co_unidade"].isin(valid_entities)]
            
            target_df["timestamp"] = t
            results.append(target_df)
            
        final_df = pd.concat(results, ignore_index=True)
        return final_df
