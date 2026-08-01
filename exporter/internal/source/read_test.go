package source

import "testing"

func TestDatabaseURLUsesPlatformFileURI(t *testing.T) {
	t.Parallel()
	for name, test := range map[string]struct {
		path            string
		operatingSystem string
		want            string
	}{
		"Unix": {
			path: "/tmp/source copies/Songs.db", operatingSystem: "linux",
			want: "file:///tmp/source%20copies/Songs.db?mode=ro&immutable=1",
		},
		"Windows": {
			path: `C:\Users\Operator\Source Copies\Songs.db`, operatingSystem: "windows",
			want: "file:///C:/Users/Operator/Source%20Copies/Songs.db?mode=ro&immutable=1",
		},
	} {
		t.Run(name, func(t *testing.T) {
			t.Parallel()
			if got := databaseURL(test.path, test.operatingSystem); got != test.want {
				t.Fatalf("databaseURL() = %q, want %q", got, test.want)
			}
		})
	}
}
