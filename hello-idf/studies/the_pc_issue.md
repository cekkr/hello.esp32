In m3_env.c in function m3_Call is passed at RunCode i_function->compiled, that is the result of GetPagePC (in m3_code.c). But these pages are not instanced in M3Memory, so it's out segmentation system. This is a whole part of the project that have to be implemented.

In case of compiled functions is a mess, because you have to force the segmentation for requesting the "next page" if necessary.

For the moment, the lack of a PSRAM seems an expensive limit to solve.

Todo: Create a sort of "segmented memory with paging" for code pages