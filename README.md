# Xamarout

Xamarin is a collection of Python classes focused on unpacking [Xamarin](https://learn.microsoft.com/en-us/xamarin/?WT.mc_id=dotnet-35129-website) assemblies.

A common use-case for this is unpacking portions of APK that were packaged with Xamarin, in which case they would appear under the `./assemblies/` directory.

## Support

Xamarout currently supports the following filetypes:

| Name | Signature |
|------|-----------|
| CompressedAssembly | `XALZ` |
| BundledAssembly | `XABA` |

## XALZ

A `CompressedAssembly` file is a file type which is essentially a LZ4 compressed `.NET` executable.

## XABA

A `BundledAssembly` is a collection of `CompressedAssembly` files, `.NET` executables, and their respective config or debug information. 

## Example

```python
import logging
from xamarout import xaba

logging.basicConfig(level=logging.DEBUG)
x = xaba.XamarinBundledAssembly("assemblies.blob")
x.write("out")
```

## Future Work

Maybe I'll turn this into a Python package at some point. There's also some more UI/UX improvements to be made, but the class structure is here to build off of.

## Further Reading & References

- https://github.com/xamarin/xamarin-android/blob/d0701eb75e096f53e3c070fc6cdbad6d7477afba/src/monodroid/jni/xamarin-app.hh
- https://github.com/x41sec/tools/blob/master/Mobile/Xamarin/Xamarin_XALZ_decompress.py
- https://www.x41-dsec.de/security/news/working/research/2020/09/22/xamarin-dll-decompression/
