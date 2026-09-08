import unittest
import numpy as np
import pandas as pd
from src import analysis as a
from src.data_processing import clean_flow, FLOW, check_unique, aggregate_weather
from src.clustering import make_features


class StatisticsTests(unittest.TestCase):
    def test_hour_mean_uses_days_not_records(self):
        f = pd.DataFrame({'date': pd.to_datetime(['2017-05-02']*2+['2017-05-03']*2),
            'station_id':[1,2,1,2], 'is_workday':[1]*4, 'hour':[8]*4,
            'inFlow':[10,20,30,40], 'outFlow':[1]*4})
        self.assertEqual(a.hourly_profile(f).iloc[0].value,50)
        self.assertEqual(a.daily_series(f).value.sum(),100)

    def test_common_dates_for_ranking(self):
        f=pd.DataFrame({'date':pd.to_datetime(['2017-05-02','2017-05-02','2017-05-03']),
            'station_id':[1,2,1],'inFlow':[10,20,100],'outFlow':[2,3,4]})
        result=a.station_ranking(f).set_index('station_id')
        self.assertEqual(result.loc[1,'value'],10)
        self.assertEqual(result.loc[2,'days'],1)

    def test_zero_balance_and_weighted_proportion(self):
        np.testing.assert_allclose(a.balance([30,10],[10,30]),[.5,-.5])
        self.assertTrue(np.isnan(a.balance([0],[0])[0]))
        f=pd.DataFrame({'inFlow':[10,90],'CinFlow':[10,0],'HBOinFlow':[0,90],'NHBinFlow':[0,0]})
        self.assertAlmostEqual(a.trip_composition(f).iloc[0]['占比'],.1)

    def test_peak_end_is_excluded(self):
        f=pd.DataFrame({'date':pd.to_datetime(['2017-05-02']*4),'station_id':[1]*4,
                        'hour':[7,8,9,17],'inFlow':[10,20,1000,8],'outFlow':[5,5,1000,8]})
        result=a.peak_direction(f)
        self.assertEqual(result.iloc[0].inFlow,30)
        self.assertEqual(result.iloc[0]['方向指数'],.5)

    def test_empty_and_bad_range(self):
        f=pd.DataFrame({'date':pd.to_datetime(['2017-05-02']),'is_valid':[True],'is_workday':[1]})
        self.assertTrue(a.filter_data(f,('2017-05-03','2017-05-04')).empty)
        with self.assertRaises(ValueError): a.filter_data(f,('2017-05-03','2017-05-01'))


class QualityTests(unittest.TestCase):
    def sample(self):
        row=dict(date='20170501',timeslot=0,startTime='060000',endTime='061000',station=112,
                 inFlow=29,outFlow=32,CinFlow=9,HBOinFlow=15,NHBinFlow=5,CoutFlow=11,HBOoutFlow=13,NHBoutFlow=8)
        return pd.DataFrame([row])

    def test_duplicates_and_conflict(self):
        row=self.sample()
        _,q=clean_flow(pd.concat([row,row]),{112})
        self.assertEqual(q['exact_duplicates_removed'],1)
        change=row.copy(); change['inFlow']=30; change['CinFlow']=10
        f,q=clean_flow(pd.concat([row,change]),{112})
        self.assertEqual(q['conflicting_rows'],2)
        self.assertFalse(f.row_valid.any())

    def test_zero_is_valid_missing_is_not(self):
        zero=self.sample(); zero[FLOW]=0
        f,q=clean_flow(zero,{112}); self.assertTrue(f.row_valid.all())
        zero.loc[0,'inFlow']=np.nan
        f,q=clean_flow(zero,{112}); self.assertFalse(f.row_valid.any())
        self.assertEqual(q['missing_cells'],1)

    def test_bad_day_flag_not_zero(self):
        row=self.sample(); row['date']='20170504'; row['timeslot']=306
        f,q=clean_flow(row,{112})
        self.assertTrue(f.known_bad_day.all()); self.assertEqual(f.iloc[0].inFlow,29)

    def test_duplicate_aux_key_fails(self):
        with self.assertRaises(ValueError):check_unique(pd.DataFrame({'id':[1,1]}),'id','表')

    def test_weather_incomplete_and_constant(self):
        w=pd.DataFrame({'time':pd.date_range('2017-05-01',periods=23,freq='h')})
        w['date']=w.time.dt.normalize()
        for col in ['temperature_2m','apparent_temperature','rain','wind_speed_10m']: w[col]=1
        result=aggregate_weather(w)
        self.assertFalse(result.iloc[0].is_valid); self.assertTrue(pd.isna(result.iloc[0].rain))


class RealDataTests(unittest.TestCase):
    def test_full_grid_and_cluster_features(self):
        from pathlib import Path
        folder=Path(__file__).resolve().parents[1]/'MetroFlow/processed'
        h=pd.read_parquet(folder/'station_hourly.parquet')
        self.assertEqual(len(h),302*123*17)
        self.assertEqual(h.loc[h.is_valid,'date'].nunique(),117)
        X,excluded=make_features(h)
        self.assertEqual(X.shape,(302,68)); self.assertEqual(excluded,[])
        np.testing.assert_allclose(X.iloc[:,:34].sum(axis=1),1)
        np.testing.assert_allclose(X.iloc[:,34:].sum(axis=1),1)
        labels=pd.read_csv(folder/'clusters/labels.csv')
        self.assertEqual(len(labels),302); self.assertEqual(labels.station_id.nunique(),302)

if __name__=='__main__': unittest.main()
