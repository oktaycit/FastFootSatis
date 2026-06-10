using IntegrationHub;
using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Web.Script.Serialization;

namespace FastFootOkcBridge
{
    internal static class OkcBridgeServer
    {
        private const int DefaultPort = 8787;
        private const int SaleTimeoutSeconds = 120;
        private const int StalePendingThresholdSeconds = 180;

        private static readonly JavaScriptSerializer Json = new JavaScriptSerializer { MaxJsonLength = int.MaxValue };
        private static readonly ConcurrentDictionary<string, PendingSale> PendingSales =
            new ConcurrentDictionary<string, PendingSale>();
        private static readonly POSCommunication Communication =
            POSCommunication.getInstance("FastFootSatis");
        private static readonly object FiscalInfoLock = new object();
        // Eşzamanlı satış isteklerini engelle — ÖKC aynı anda tek işlem yapabilir
        private static readonly SemaphoreSlim SaleLock = new SemaphoreSlim(1, 1);
        private static readonly DateTime BridgeStartedAt = DateTime.Now;

        private static volatile bool _deviceConnected;
        private static volatile bool _deviceStateKnown;
        private static volatile bool _fiscalInfoLoaded;
        private static volatile int _lastSerialCallbackType = -1;
        private static string _lastDeviceId = "";
        private static string _lastFiscalInfo = "";
        private static string _lastDeviceStateAt = "";
        private static string _lastSerialCallbackAt = "";

        private sealed class PendingSale
        {
            private readonly ManualResetEventSlim _done = new ManualResetEventSlim(false);

            public PendingSale()
            {
                Status = -1;
                Message = "";
                RawSaleInfo = "";
            }

            public string BasketId { get; set; }
            public ManualResetEventSlim Done { get { return _done; } }
            public bool Success { get; set; }
            public int Status { get; set; }
            public string Message { get; set; }
            public int ReceiptNo { get; set; }
            public int ZNo { get; set; }
            public string RawSaleInfo { get; set; }
            public DateTime CreatedAt { get; set; }
        }

        [STAThread]
        private static void Main(string[] args)
        {
            var port = GetPort(args);
            var prefix = string.Format("http://+:{0}/", port);

            Communication.setDeviceStateCallback(DeviceStateCallback);
            Communication.setSerialInCallback(SerialInCallback);

            var listener = new HttpListener();
            listener.Prefixes.Add(prefix);
            listener.Start();

            Console.WriteLine(string.Format("FastFood OKC Bridge dinliyor: {0}", prefix));
            Console.WriteLine("Endpointler: GET /health, POST /api/sale, GET /api/fiscal-info");
            Console.WriteLine("Cikis icin Ctrl+C.");
            Console.WriteLine("Not: deviceStateKnown=false ise IntegrationHub cihaz state callback'i henuz gelmemistir; satis yine de denenir.");

            var listenerThread = new Thread(delegate() { ListenForRequests(listener); });
            listenerThread.IsBackground = true;
            listenerThread.Start();

            StartCallbackWatchdog();

            while (true)
            {
                Application.DoEvents();
                Thread.Sleep(10);  // 50ms → 10ms: Callback tepki süresini iyileştir
            }
        }

        private static void StartCallbackWatchdog()
        {
            var watchdogThread = new Thread(delegate()
            {
                Thread.Sleep(30000);
                if (!_deviceStateKnown)
                {
                    Console.WriteLine(string.Format(
                        "{0:yyyy-MM-dd HH:mm:ss} UYARI: OKC cihaz state callback'i henuz gelmedi. USB init loglari gorunuyorsa satis yine de sendBasket ile denenecek.",
                        DateTime.Now));
                }
            });
            watchdogThread.IsBackground = true;
            watchdogThread.Start();
        }

        private static void ListenForRequests(HttpListener listener)
        {
            while (true)
            {
                try
                {
                    var context = listener.GetContext();
                    ThreadPool.QueueUserWorkItem(delegate { HandleRequest(context); });
                }
                catch (Exception ex)
                {
                    Console.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss} HTTP listener error: {1}", DateTime.Now, ex.Message));
                    Thread.Sleep(1000);
                }
            }
        }

        private static int GetPort(string[] args)
        {
            int fromArgs;
            if (args.Length > 0 && int.TryParse(args[0], out fromArgs))
            {
                return fromArgs;
            }

            var fromEnv = Environment.GetEnvironmentVariable("OKC_BRIDGE_PORT");
            int port;
            if (int.TryParse(fromEnv, out port))
            {
                return port;
            }

            return DefaultPort;
        }

        private static void DeviceStateCallback(bool isConnected, string id)
        {
            _deviceStateKnown = true;
            _deviceConnected = isConnected;
            _lastDeviceId = id ?? "";
            _lastDeviceStateAt = FormatTimestamp(DateTime.Now);
            if (!isConnected)
            {
                _fiscalInfoLoaded = false;
                _lastFiscalInfo = "";
            }
            Console.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss} OKC device state: {1} {2}", DateTime.Now, isConnected, id));
        }

        private static void SerialInCallback(int type, string value)
        {
            _lastSerialCallbackType = type;
            _lastSerialCallbackAt = FormatTimestamp(DateTime.Now);
            Console.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss} OKC callback type={1}", DateTime.Now, type));

            if (type == 3)
            {
                CompletePendingSale(value);
            }
        }

        private static void CompletePendingSale(string saleInfoJson)
        {
            var saleInfo = DeserializeObject(saleInfoJson);
            var basketId = GetString(saleInfo, "basketID");

            PendingSale pending = null;
            if (!string.IsNullOrWhiteSpace(basketId))
            {
                PendingSales.TryRemove(basketId, out pending);
            }
            else if (PendingSales.Count == 1)
            {
                var first = PendingSales.First();
                PendingSales.TryRemove(first.Key, out pending);
            }

            if (pending == null)
            {
                Console.WriteLine("Eslesen bekleyen satis bulunamadi.");
                return;
            }

            pending.RawSaleInfo = saleInfoJson;
            pending.Status = GetInt(saleInfo, "status", -1);
            pending.Success = pending.Status == 0;
            pending.Message = GetString(saleInfo, "message");
            pending.ReceiptNo = GetInt(saleInfo, "receiptNo", 0);
            pending.ZNo = GetInt(saleInfo, "zNo", 0);
            pending.Done.Set();
        }

        private static void HandleRequest(HttpListenerContext context)
        {
            try
            {
                var path = context.Request.Url.AbsolutePath.TrimEnd('/').ToLowerInvariant();

                if (context.Request.HttpMethod == "GET" && path == "/health")
                {
                    WriteJson(context, new Dictionary<string, object>
                    {
                        { "success", true },
                        { "bridgeReady", true },
                        { "bridgeStartedAt", FormatTimestamp(BridgeStartedAt) },
                        { "uptimeSeconds", Convert.ToInt32((DateTime.Now - BridgeStartedAt).TotalSeconds) },
                        { "deviceStateKnown", _deviceStateKnown },
                        { "deviceConnected", _deviceConnected },
                        { "deviceId", _lastDeviceId },
                        { "lastDeviceStateAt", _lastDeviceStateAt },
                        { "lastSerialCallbackAt", _lastSerialCallbackAt },
                        { "lastSerialCallbackType", _lastSerialCallbackType },
                        { "pendingSales", PendingSales.Count },
                        { "message", GetDeviceStatusMessage() }
                    });
                    return;
                }

                if (context.Request.HttpMethod == "GET" && path == "/api/fiscal-info")
                {
                    WriteJson(context, new Dictionary<string, object>
                    {
                        { "success", true },
                        { "bridgeReady", true },
                        { "bridgeStartedAt", FormatTimestamp(BridgeStartedAt) },
                        { "uptimeSeconds", Convert.ToInt32((DateTime.Now - BridgeStartedAt).TotalSeconds) },
                        { "deviceStateKnown", _deviceStateKnown },
                        { "deviceConnected", _deviceConnected },
                        { "lastDeviceStateAt", _lastDeviceStateAt },
                        { "lastSerialCallbackAt", _lastSerialCallbackAt },
                        { "lastSerialCallbackType", _lastSerialCallbackType },
                        { "fiscalInfo", _lastFiscalInfo },
                        { "message", "Live fiscalInfo sorgusu kapali; POS DLL bu cagriyi bazi kurulumlarda sonlandirabiliyor." }
                    });
                    return;
                }

                if (context.Request.HttpMethod == "POST" && path == "/api/sale")
                {
                    HandleSale(context);
                    return;
                }

                WriteJson(context, new Dictionary<string, object>
                {
                    { "success", false },
                    { "message", "Endpoint bulunamadi" }
                }, 404);
            }
            catch (Exception ex)
            {
                WriteJson(context, new Dictionary<string, object>
                {
                    { "success", false },
                    { "message", ex.Message }
                }, 500);
            }
        }

        private static string GetDeviceStatusMessage()
        {
            if (!_deviceStateKnown)
            {
                return "OKC cihaz durumu henuz callback ile bildirilmedi; satis istegi gelirse denenecek.";
            }

            return _deviceConnected ? "OKC cihazi bagli." : "OKC cihazi bagli degil.";
        }

        private static string FormatTimestamp(DateTime value)
        {
            return value.ToString("yyyy-MM-dd HH:mm:ss");
        }

        private static void HandleSale(HttpListenerContext context)
        {
            var body = ReadBody(context.Request);
            if (string.IsNullOrWhiteSpace(body))
            {
                WriteJson(context, new Dictionary<string, object>
                {
                    { "success", false },
                    { "message", "Bos sepet istegi" }
                }, 400);
                return;
            }

            var basket = DeserializeObject(body);
            var basketId = GetString(basket, "basketID");
            if (string.IsNullOrWhiteSpace(basketId))
            {
                WriteJson(context, new Dictionary<string, object>
                {
                    { "success", false },
                    { "message", "basketID zorunlu" }
                }, 400);
                return;
            }

            // Eski tamamlanmamış işlemleri temizle (StalePendingThresholdSeconds'den eski)
            CleanStalePendingSales();

            // Eşzamanlı satış engeli — ÖKC aynı anda tek işlem yapabilir
            if (!SaleLock.Wait(TimeSpan.FromSeconds(10)))
            {
                Console.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss} UYARI: Esanli satis istegi reddedildi, baska islem devam ediyor", DateTime.Now));
                WriteJson(context, new Dictionary<string, object>
                {
                    { "success", false },
                    { "message", "Baska bir OKC islemi devam ediyor, lutfen bekleyin" }
                }, 429);
                return;
            }

            try
            {
                var pending = new PendingSale { BasketId = basketId, CreatedAt = DateTime.Now };
                PendingSales[basketId] = pending;

                Console.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss} Satis basladi: {1}", DateTime.Now, basketId));
                var sendStatus = Communication.sendBasket(body);
                if (sendStatus != 1)
                {
                    PendingSale removed;
                    PendingSales.TryRemove(basketId, out removed);
                    Console.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss} sendBasket basarisiz: status={1}", DateTime.Now, sendStatus));
                    WriteJson(context, new Dictionary<string, object>
                    {
                        { "success", false },
                        { "message", "IntegrationHub sendBasket basarisiz dondu" },
                        { "sendStatus", sendStatus },
                        { "deviceStateKnown", _deviceStateKnown },
                        { "deviceConnected", _deviceConnected }
                    }, 502);
                    return;
                }

                if (!pending.Done.Wait(TimeSpan.FromSeconds(SaleTimeoutSeconds)))
                {
                    PendingSale removed;
                    PendingSales.TryRemove(basketId, out removed);
                    Console.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss} ZAMAN ASIMI: {1} ({2}s)", DateTime.Now, basketId, SaleTimeoutSeconds));
                    WriteJson(context, new Dictionary<string, object>
                    {
                        { "success", false },
                        { "message", "OKC satis callback zaman asimi" },
                        { "deviceStateKnown", _deviceStateKnown },
                        { "deviceConnected", _deviceConnected }
                    }, 504);
                    return;
                }

                Console.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss} Satis tamamlandi: {1} status={2}", DateTime.Now, basketId, pending.Status));
                WriteJson(context, new Dictionary<string, object>
                {
                    { "success", pending.Success },
                    { "status", pending.Status },
                    { "message", string.IsNullOrWhiteSpace(pending.Message) ? "OK" : pending.Message },
                    { "receiptNo", pending.ReceiptNo },
                    { "zNo", pending.ZNo },
                    { "basketID", pending.BasketId },
                    { "rawSaleInfo", pending.RawSaleInfo }
                }, pending.Success ? 200 : 502);
            }
            finally
            {
                SaleLock.Release();
            }
        }

        /// <summary>
        /// StalePendingThresholdSeconds'den eski bekleyen satışları temizle.
        /// Bu, timeout sonrası kalan "hayalet" pending entry'leri temizler.
        /// </summary>
        private static void CleanStalePendingSales()
        {
            var threshold = DateTime.Now.AddSeconds(-StalePendingThresholdSeconds);
            foreach (var kvp in PendingSales)
            {
                if (kvp.Value.CreatedAt < threshold)
                {
                    PendingSale removed;
                    if (PendingSales.TryRemove(kvp.Key, out removed))
                    {
                        Console.WriteLine(string.Format("{0:yyyy-MM-dd HH:mm:ss} Eski bekleyen satis temizlendi: {1}", DateTime.Now, kvp.Key));
                    }
                }
            }
        }

        private static string GetFiscalInfo()
        {
            lock (FiscalInfoLock)
            {
                if (_fiscalInfoLoaded && !string.IsNullOrWhiteSpace(_lastFiscalInfo))
                {
                    return _lastFiscalInfo;
                }

                _lastFiscalInfo = Communication.getFiscalInfo();
                _fiscalInfoLoaded = !string.IsNullOrWhiteSpace(_lastFiscalInfo);
                return _lastFiscalInfo;
            }
        }

        private static string ReadBody(HttpListenerRequest request)
        {
            using (var reader = new StreamReader(request.InputStream, request.ContentEncoding ?? Encoding.UTF8))
            {
                return reader.ReadToEnd();
            }
        }

        private static Dictionary<string, object> DeserializeObject(string json)
        {
            return Json.Deserialize<Dictionary<string, object>>(json);
        }

        private static string GetString(IDictionary<string, object> data, string key)
        {
            object value;
            if (data == null || !data.TryGetValue(key, out value) || value == null)
            {
                return "";
            }

            return Convert.ToString(value);
        }

        private static int GetInt(IDictionary<string, object> data, string key, int fallback)
        {
            object value;
            if (data == null || !data.TryGetValue(key, out value) || value == null)
            {
                return fallback;
            }

            try
            {
                return Convert.ToInt32(value);
            }
            catch
            {
                return fallback;
            }
        }

        private static void WriteJson(HttpListenerContext context, object payload, int statusCode = 200)
        {
            var json = Json.Serialize(payload);
            var bytes = Encoding.UTF8.GetBytes(json);

            context.Response.StatusCode = statusCode;
            context.Response.ContentType = "application/json; charset=utf-8";
            context.Response.ContentLength64 = bytes.Length;
            context.Response.OutputStream.Write(bytes, 0, bytes.Length);
            context.Response.OutputStream.Close();
        }
    }
}
