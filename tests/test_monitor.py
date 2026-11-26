import unittest

from aegis_reconnect.monitor import Event, Monitor, MonitorSettings, Observation, Reason


class Driver:
    def __init__(self, **settings):
        base = dict(outage_after_failures=3, stable_seconds=10, grace_seconds=60,
                    server_down_failures=2, unknown_drop_seconds=20, hung_seconds=20)
        base.update(settings)
        self.monitor = Monitor(MonitorSettings(**base))
        self.t = 0.0

    def step(self, internet=True, running=True, connected=True, server=None, hung=False, dt=5.0):
        self.t += dt
        return self.monitor.update(Observation(self.t, internet, running, connected, server, hung))

    @staticmethod
    def events(occurrences):
        return [o.event for o in occurrences]

    def run(self, count, **kw):
        seen = []
        for _ in range(count):
            seen += self.step(**kw)
        return seen


class NetworkOutageTest(unittest.TestCase):
    def setUp(self):
        self.d = Driver()

    def test_healthy_session_stays_quiet(self):
        self.assertEqual(self.d.events(self.d.step()), [Event.GAME_STARTED])
        self.assertEqual(self.d.run(20), [])

    def test_wifi_trip_that_kills_the_connection_asks_for_reconnect(self):
        self.d.step()
        self.d.run(2, internet=False)
        self.assertEqual(self.d.events(self.d.step(internet=False)), [Event.OUTAGE_STARTED])
        self.d.step(internet=False, connected=False)
        self.d.run(2, connected=False)
        got = self.d.step(connected=False)
        self.assertEqual(self.d.events(got), [Event.INTERNET_RESTORED, Event.RECONNECT_NEEDED])
        self.assertEqual(got[-1].reason, Reason.NETWORK)
        self.assertEqual(self.d.run(3, connected=False), [])

    def test_short_trip_where_the_game_survives_needs_no_action(self):
        self.d.step()
        self.d.run(3, internet=False)
        seen = self.d.run(16)
        kinds = [o.event for o in seen]
        self.assertIn(Event.GAME_SURVIVED, kinds)
        self.assertNotIn(Event.RECONNECT_NEEDED, kinds)

    def test_outage_while_not_connected_does_nothing(self):
        self.d.step(connected=False)
        self.d.run(3, internet=False, connected=False)
        seen = self.d.run(6, connected=False)
        self.assertNotIn(Event.RECONNECT_NEEDED, [o.event for o in seen])

    def test_flapping_internet_does_not_declare_an_outage(self):
        self.d.step()
        seen = []
        for i in range(20):
            seen += self.d.step(internet=(i % 2 == 0))
        self.assertNotIn(Event.OUTAGE_STARTED, [o.event for o in seen])

    def test_game_closing_cancels_a_pending_reconnect(self):
        self.d.step()
        self.d.run(3, internet=False)
        self.d.step(internet=False, connected=False)
        seen = self.d.run(4, running=False, connected=False)
        kinds = [o.event for o in seen]
        self.assertIn(Event.GAME_STOPPED, kinds)
        self.assertNotIn(Event.RECONNECT_NEEDED, kinds)


class ServerDropTest(unittest.TestCase):
    def test_kick_or_client_error_is_reported_never_acted_on(self):
        d = Driver()
        d.step()
        self.assertEqual(d.events(d.step(connected=False, server=True)), [Event.DISCONNECTED_ONLINE])
        seen = d.run(6, connected=False, server=True)
        kinds = [o.event for o in seen]
        self.assertIn(Event.DROP_NOT_ACTED, kinds)
        self.assertNotIn(Event.RECONNECT_NEEDED, kinds)

    def test_server_that_goes_down_and_comes_back_is_reconnected(self):
        d = Driver()
        d.step()
        d.step(connected=False, server=False)
        got = d.step(connected=False, server=False)
        self.assertEqual(d.events(got), [Event.SERVER_DOWN])
        d.run(2, connected=False, server=False)
        seen = d.run(5, connected=False, server=True)
        kinds = [o.event for o in seen]
        self.assertEqual(kinds, [Event.SERVER_BACK, Event.RECONNECT_NEEDED])
        self.assertEqual(seen[-1].reason, Reason.SERVER)

    def test_opt_in_reconnects_after_an_unexplained_drop(self):
        d = Driver(reconnect_on_unknown=True)
        d.step()
        d.step(connected=False, server=True)
        seen = d.run(6, connected=False, server=True)
        reconnects = [o for o in seen if o.event is Event.RECONNECT_NEEDED]
        self.assertEqual(len(reconnects), 1)
        self.assertEqual(reconnects[0].reason, Reason.UNKNOWN)

    def test_unknown_server_address_falls_back_to_unexplained(self):
        d = Driver()
        d.step()
        d.step(connected=False, server=None)
        kinds = [o.event for o in d.run(6, connected=False, server=None)]
        self.assertIn(Event.DROP_NOT_ACTED, kinds)

    def test_manual_reconnect_cancels_the_watch(self):
        d = Driver()
        d.step()
        d.step(connected=False, server=False)
        d.step(connected=True)
        seen = d.run(10, connected=True)
        self.assertEqual([o.event for o in seen], [])

    def test_internet_dying_hands_over_to_the_network_path(self):
        d = Driver()
        d.step()
        d.step(connected=False, server=True)
        seen = d.run(3, internet=False, connected=False)
        self.assertEqual([o.event for o in seen], [Event.OUTAGE_STARTED])


class FrozenTest(unittest.TestCase):
    def test_reported_once_after_the_threshold(self):
        d = Driver()
        d.step()
        seen = d.run(8, hung=True)
        self.assertEqual([o.event for o in seen].count(Event.GAME_FROZEN), 1)

    def test_a_short_stall_is_not_reported(self):
        d = Driver()
        d.step()
        seen = d.run(2, hung=True) + d.run(3, hung=False)
        self.assertEqual(seen, [])

    def test_reports_again_after_recovering_and_freezing_again(self):
        d = Driver()
        d.step()
        first = d.run(6, hung=True)
        d.run(2, hung=False)
        second = d.run(6, hung=True)
        self.assertEqual([o.event for o in first + second].count(Event.GAME_FROZEN), 2)


if __name__ == "__main__":
    unittest.main()
