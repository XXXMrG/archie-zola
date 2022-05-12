+++
title = "浅谈 tauri"
date = 2022-02-18
description = "本文旨在介绍 tauri 的相关背景知识、性能及可用性表现、以及一点架构设计思想。"

[taxonomies]
tags = ["FE", "Rust"]
+++

本文旨在介绍 tauri 的相关背景知识、性能及可用性表现、以及一点架构设计思想。

## 背景

---

[tauri](https://github.com/tauri-apps/tauri) 用于构建跨平台桌面应用，对标的是 [electron](https://github.com/electron/electron)，但完全由 rust 开发。

跟随 rust 的生态发展，tauri 在 2021 年的 GitHub star 数增长迅猛。

目前最新的版本为 1.0.0-beta.8，于 2021 年 8 月发布。

![star-history](/imgs/star-history.png)

Tauri 的设计思路与 electron 基本完全一致，即「使用 JavaScript，HTML 和 CSS 构建跨平台的桌面应用程序」，最后的应用由 Web APP + Native Backend 组成。

- Web APP 依托于现代前端技术，负责构建在各个平台下，效果基本一致的图形化界面。
- Native Backend 则负责与操作系统交互，为 Web APP 拓展一些原生的能力。

这种设计要比使用传统的 GUI 库构建桌面应用容易得多，但最后应用的图形界面还是需要运行在浏览器引擎的基础之上。

最早使用这种设计方式的 electron 由于其相当低的上手难度和 Javascript 极其丰富的社区生态，在最近 GitHub 上的 star 数量达到了夸张的 100k；<mark class="notice">但其为人诟病的最多的一点，就是怎样都无法优化的、颇为庞大的应用体积。</mark>

接下来让我们看看 tauri 在应用体积、运行开销、性能等指标上，是怎样做到对 electron 的「碾压般」的提升的。

## 对比

---

> 所有数据来自于 [https://tauri.studio/benchmarks](https://tauri.studio/benchmarks)

**产物体积对比：**

2.74MB / 127.74MB

electron 由于需要打包 chromium 和 V8 runtime，在应用体积方面，tauri 自然是有相当大的优势，更小的应用体积对桌面应用的分发和用户的体验都能带来正向的提升。

![vs-01](/imgs/vs-01.png)

**内存占用对比：**

Tauri 由于使用 rust 作为与系统交互的后端，语言层面上就要更贴近系统级，因此内存开销方面相比 V8 要小很多。
![vs-02](/imgs/vs-02.png)

**功能以及运行环境对比：**

运行环境方面，tauri 使用 WRY 作为与渲染引擎交互的中间层（具体我们后面会讲到），并且与操作系统交互的后端也完全由 rust 完成；不同于 javascript 生态，tauri 最后的产物中 rust 的部分均会被编译成二进制格式，因此无需包含 runtime，也能大大增加应用逆向解包的成本。

而二者在功能上差异不大，<mark>但 tauri 明确表示有支持移动端应用的计划。</mark>

![vs-03](/imgs/vs-03.png)

## 架构设计

---

> 参考：[tauri/ARCHITECTURE.md at dev · tauri-apps/tauri · GitHub](https://github.com/tauri-apps/tauri/blob/dev/ARCHITECTURE.md)

### 整体流程

Tauri 的整体架构，自顶向下可以分为三层：

1. tauri-app：整合所有模块，读取项目配置，完成最终 APP 产物的打包；主要负责初始化 Web APP 与底层系统 API 的通信环境，注入全局 API，管理应用更新等。
2. [WRY](https://github.com/tauri-apps/wry)：一个跨平台 Webview 渲染库，会根据各平台选择特定的浏览器引擎启动 Webview，抹平平台差异，暴露统一的上层 API。
3. [TAO](https://github.com/tauri-apps/tao)：跨平台应用窗口管理器，主要用于构建各平台下的应用主窗口。

![arch-01](/imgs/arch-01.png)

Tauri 除了完全使用 rust 开发以外，与 electron 最大的不同之处就在于，没有使用直接为每个应用单独集成一个 chromium 环境，而是直接使用操作系统内置的浏览器引擎执行 Web APP，也就是这里提到的：WRY。

在当前版本的 WRY 中，各平台下的浏览器引擎选取规则如下：

![arch-02](/imgs/arch-02.png)

简单看一下 WRY 在 macOS 下是如何启动一个 webview 的

```rust
fn main() -> wry::Result<()> {
  use wry::{
    application::{
      event::{Event, StartCause, WindowEvent},
      event_loop::{ControlFlow, EventLoop},
      window::WindowBuilder,
    },
    webview::WebViewBuilder,
  };

  // 此处的 event_loop 非 js 的 event loop，而是 tao 用来响应窗口事件的
  let event_loop = EventLoop::new();

  // 新建一个窗口
  let window = WindowBuilder::new()
    .with_title("Hello World")
    .build(&event_loop)?;

  // 在该窗口启动一个 webview
  let webview = WebViewBuilder::new(window)?
    .with_url("https://vhsagj.smartapps.baidu.com/")?
    .build()?;

  // 启动 event loop
  event_loop.run(move |event, _, control_flow| {
    *control_flow = ControlFlow::Wait;

    match event {
      Event::NewEvents(StartCause::Init) => println!("Wry has started!"),
      Event::WindowEvent {
        event: WindowEvent::CloseRequested,
        ..
      } => *control_flow = ControlFlow::Exit,
      _ => {
        dbg!(webview.window().inner_size());
      }
    }
  });
}
```

编译并执行以上 rust 代码，就会启动一个窗口，使用右键点击则可以开启 inspector：

![demo-01](/imgs/demo-01.png)

先不关心窗口管理相关的逻辑，接下来主要关注这几行代码，让我们深入看看 WRY 是怎么启动 webview 的。

```rust
  // 在该窗口启动一个 webview
  let webview = WebViewBuilder::new(window)?
    .with_url("https://vhsagj.smartapps.baidu.com/")?
    .build()?;
```

WebViewBuilder 是 WRY 暴露出来的接口，主要进行一些在启动系统 webview 之前的配置封装和初始化工作；在获取到 TAO 的 window 窗口对象后并初始化配置后，会开始调用系统的 API，来启动 webview，在 macOS 上，这通过调用 objc 代码来实现。

Rust 与 objc 运行时的绑定则依赖 [https://crates.io/crates/objc](https://crates.io/crates/objc) 。

上面的代码最后会调用 macOS 系统提供的 webkit 接口来新建一个 WKWebview。具体实现参见： [https://github.com/tauri-apps/wry/blob/dev/src/webview/wkwebview/mod.rs](https://github.com/tauri-apps/wry/blob/dev/src/webview/wkwebview/mod.rs%EF%BC%8C)

这里不再赘述，在各个平台下，WRY 内部的处理逻辑基本与此类似。

综上所述，tauri 整体的设计思路与 electron 不同之处可以总结为以下两点：

1. 舍弃 chromium，直接使用操作系统内置的浏览器引擎，通过 WRY 来抹平浏览器的接口差异，**但前端应用在运行时实际上还是可能会遇到平台兼容性问题。**
2. 舍弃 node.js 运行时，使用 rust 与操作系统交互。

### 如何通信？

TL;DR

**在 WRY 这一层，会基于各平台 Webview 暴露的 JS 到 Webview native 的接口，使用** [JSON-RPC](https://www.jsonrpc.org/) **作为通信格式，并抹平平台差异。**

Tauri 提供了「指令系统」，用来做 JS 与 rust 的异步通信。

在 macOS 上，JS 到 native 层是基于 [WKScriptMessageHandler](https://developer.apple.com/documentation/webkit/wkscriptmessagehandler) 实现的；WRY 会在创建 Webview 的时候，使用 [addScriptMessageHandler](https://developer.apple.com/documentation/webkit/wkusercontentcontroller/1537172-addscriptmessagehandler?language=objc) 注册一个全局通信函数到 JS context，并传入用于接收消息的函数指针。

```rust
// Message handler
  let rpc_handler_ptr = if let Some(rpc_handler) = attributes.rpc_handler {
    let cls = ClassDecl::new("WebViewDelegate", class!(NSObject));
    let cls = match cls {
      Some(mut cls) => {
        cls.add_ivar::<*mut c_void>("function");
        cls.add_method(
          sel!(userContentController:didReceiveScriptMessage:),
          // did_receive 是一个 extern 函数，在 messageHandlers 接收到 JS 传来的消息时会被调用。
          did_receive as extern "C" fn(&Object, Sel, id, id),
        );
        cls.register()
      }
      None => class!(WebViewDelegate),
    };
    let handler: id = msg_send![cls, new];
    let rpc_handler_ptr = Box::into_raw(Box::new((rpc_handler, window.clone())));

    // 这里将 rpc_handler 的指针保存到了一个 objc 对象上的 function 字段上。在 did_receive 时会取出来。
    (*handler).set_ivar("function", rpc_handler_ptr as *mut _ as *mut c_void);
    let external = NSString::new("external");
    // 此处会为 JS context 绑定一个全局函数： window.webkit.messageHandlers.<name>.postMessage(<messageBody>)
    let _: () = msg_send![manager, addScriptMessageHandler:handler name:external];
    rpc_handler_ptr
  } else {
    null_mut()
  };
```

基于 webkit 提供的通信能力，WRY 会再暴露一个经过简单封装的 RPC 处理逻辑，这也是最后 [ tauri Javascript API ](https://github.com/tauri-apps/tauri/tree/dev/tooling/api) 中的底层逻辑：

1. 将数据包装为 JSON-RPC 的格式。
2. 在全局维护一个 promise 队列，用于触发异步回调。

```javascript
// 在启动 webview 的同时，WRY 会注入这样一段 JS 代码到全局
(function () {
  function Rpc() {
    const self = this;
    this._promises = {};

    // 当任务完成，会通过 evaluateJavaScript 来执行此处的代码，触发 promise
    // Private internal function called on error
    this._error = (id, error) => {
      if (this._promises[id]) {
        this._promises[id].reject(error);
        delete this._promises[id];
      }
    };

    // Private internal function called on result
    this._result = (id, result) => {
      if (this._promises[id]) {
        this._promises[id].resolve(result);
        delete this._promises[id];
      }
    };

    // Call remote method and expect a reply from the handler
    // 需要回调时，保存一个 promise 到全局队列
    this.call = function (method) {
      let array = new Uint32Array(1);
      window.crypto.getRandomValues(array);
      const id = array[0];
      const params = Array.prototype.slice.call(arguments, 1);
      const payload = { jsonrpc: "2.0", id, method, params };
      const promise = new Promise((resolve, reject) => {
        self._promises[id] = { resolve, reject };
      });
      window.external.invoke(JSON.stringify(payload));
      return promise;
    };

    // Send a notification without an `id` so no reply is expected.
    this.notify = function (method) {
      const params = Array.prototype.slice.call(arguments, 1);
      const payload = { jsonrpc: "2.0", method, params };
      window.external.invoke(JSON.stringify(payload));
      return Promise.resolve();
    };
  }
  window.external = window.external || {};
  window.external.rpc = new Rpc();
  window.rpc = window.external.rpc;
})();
```

**基于这样的通信架构，tauri 可以实现使用前端（JS）作为应用主逻辑，而将一些需要高性能、调用系统能力的任务，通过指令丢给 rust 去做。**

## 总结

---

想要打败 electron 的选手很多，但目前看 tauri 可能是最接近成功的一位了。
为了解决 electron 的体积问题，tauri 选择直接使用系统内置的 webview，这样的选择也是基于目前的发展趋势的，即<mark>各家操作系统内置的浏览器生态在不断进步，尤其是之前被大多数人诟病的 Windows 平台</mark>。微软对新版 Edge 中内置的 webview2 青眼有加，大型的桌面应用如 Office，outlook 都在推进升级至 webview2。从趋势上来看，操作系统内置的浏览器生态是在不断进步的，tauri 自然也能享受到这些红利。

而 rust 语言的逐渐繁荣，也更加推动了 tauri 的生态发展，大量的贡献者在短时间内快速融入开源社区，tauri 的核心开发团队也始终坚持着 FLOSS （自由及开放源代码软件）的开放态度，这都使得 tauri 更具有成为成熟的解决方案的潜力。

但目前的版本仍处于快速迭代期，还存在一些问题：

- 对于前端网页而言，实际上并没有完全抹平平台差异，前端开发时仍需要考虑<mark>**平台兼容性。**</mark>
- 线下测试来看，webview 和 rust 的性能虽然足够好，但在一些旧的设备上，窗口和 webview 创建的耗时<mark>**仍然不可忽视。**</mark>
- 存在很多 bug，这些 bug 大多不直接来自于 tauri，而是来自于各平台下的 webview 接口，因此<mark>**bug 的解决周期也都相当长，目前很难直接用于生产环境。**</mark>
- 文档和社区还是不够完善，大多数时间还需要<mark>**自己扒代码**</mark>。（但正在快速发展，就在这篇文档写完的时候，大概两周左右的时间，官网的文档就经历了大规模的优化和更新）
